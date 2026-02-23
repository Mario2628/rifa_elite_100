import json
from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import and_

from app.extensions import db, limiter
from app.models import (
    AdminUser, AuditLog,
    Raffle, Ticket, TicketStatus,
    Purchase, PurchaseStatus,
    Winners, generate_folio
)
from app.forms import (
    AdminLoginForm, AdminChangePasswordForm, AdminCreateUserForm, WinnerForm, AdminNoteForm,
    ManualPurchaseForm
)
from app.security import validate_password_policy
from app.admin.utils import build_whatsapp_paid_message, build_wa_link

from io import BytesIO
from openpyxl import Workbook
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def log_audit(action: str, entity_type: str = None, entity_id: int = None, meta: dict = None):
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    entry = AuditLog(
        admin_user_id=current_user.id if current_user.is_authenticated else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        meta_json=json.dumps(meta or {}, ensure_ascii=False),
        ip_address=ip,
    )
    db.session.add(entry)
    db.session.commit()


def begin_clean():
    """
    SQLAlchemy 2.x inicia transacción automática (autobegin) en el primer SELECT.
    Si luego llamas session.begin() truena con:
      InvalidRequestError: A transaction is already begun on this Session.

    Solución: rollback para cerrar la transacción automática y abrir una controlada.
    """
    try:
        db.session.rollback()
    except Exception:
        pass
    return db.session.begin()


def get_active_raffle():
    raffle = Raffle.query.filter_by(is_active=True).order_by(Raffle.id.desc()).first()
    if not raffle:
        raise RuntimeError("No hay rifa activa. Ejecuta 'flask seed'.")
    return raffle


@admin_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("50 per hour")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard"))

    form = AdminLoginForm()
    if request.method == "GET":
        return render_template("admin/login.html", form=form)

    if not form.validate_on_submit():
        flash("Completa usuario y contraseña.", "error")
        return render_template("admin/login.html", form=form), 400

    username = form.username.data.strip()
    password = form.password.data

    user = AdminUser.query.filter_by(username=username).first()
    if not user or not user.is_active:
        flash("Credenciales inválidas.", "error")
        return render_template("admin/login.html", form=form), 401

    if user.is_locked():
        flash("Usuario bloqueado temporalmente por intentos fallidos. Intenta más tarde.", "error")
        return render_template("admin/login.html", form=form), 403

    if not user.check_password(password):
        user.register_failed_login()
        db.session.commit()
        log_audit("LOGIN_FAILED", "AdminUser", user.id, {"username": username})
        flash("Credenciales inválidas.", "error")
        return render_template("admin/login.html", form=form), 401

    user.reset_login_failures()
    user.last_login_at = datetime.utcnow()
    db.session.commit()

    login_user(user)
    log_audit("LOGIN_OK", "AdminUser", user.id, {"username": username})

    if user.must_change_password:
        return redirect(url_for("admin.change_password"))

    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/logout")
@login_required
def logout():
    log_audit("LOGOUT", "AdminUser", current_user.id, {"username": current_user.username})
    logout_user()
    return redirect(url_for("admin.login"))


@admin_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    form = AdminChangePasswordForm()
    if request.method == "GET":
        return render_template("admin/change_password.html", form=form)

    if not form.validate_on_submit():
        flash("Completa el formulario.", "error")
        return render_template("admin/change_password.html", form=form), 400

    if not current_user.check_password(form.current_password.data):
        flash("Contraseña actual incorrecta.", "error")
        return render_template("admin/change_password.html", form=form), 401

    if form.new_password.data != form.confirm_password.data:
        flash("La confirmación no coincide.", "error")
        return render_template("admin/change_password.html", form=form), 400

    ok, msg = validate_password_policy(form.new_password.data)
    if not ok:
        flash(msg, "error")
        return render_template("admin/change_password.html", form=form), 400

    current_user.set_password(form.new_password.data)
    current_user.must_change_password = False
    db.session.commit()
    log_audit("PASSWORD_CHANGED", "AdminUser", current_user.id, {"username": current_user.username})
    flash("Contraseña actualizada.", "success")
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/")
@login_required
def dashboard():
    raffle = get_active_raffle()
    total = Ticket.query.filter_by(raffle_id=raffle.id).count()
    free = Ticket.query.filter_by(raffle_id=raffle.id, status=TicketStatus.FREE).count()
    reserved = Ticket.query.filter_by(raffle_id=raffle.id, status=TicketStatus.RESERVED).count()
    paid = Ticket.query.filter_by(raffle_id=raffle.id, status=TicketStatus.PAID).count()

    pending = Purchase.query.filter_by(raffle_id=raffle.id, status=PurchaseStatus.PENDING).count()
    approved = Purchase.query.filter_by(raffle_id=raffle.id, status=PurchaseStatus.APPROVED).count()
    paid_p = Purchase.query.filter_by(raffle_id=raffle.id, status=PurchaseStatus.PAID).count()

    total_sold_mxn = paid * raffle.ticket_price_mxn

    return render_template(
        "admin/dashboard.html",
        raffle=raffle,
        total=total,
        free=free,
        reserved=reserved,
        paid=paid,
        pending=pending,
        approved=approved,
        paid_p=paid_p,
        total_sold_mxn=total_sold_mxn
    )


@admin_bp.route("/tickets", methods=["GET"])
@login_required
def tickets_manage():
    raffle = get_active_raffle()

    query_num = request.args.get("q", "").strip()
    ticket = None
    purchase = None

    if query_num:
        try:
            n = int(query_num)
            ticket = Ticket.query.filter_by(raffle_id=raffle.id, number=n).first()
            if ticket:
                purchase = (
                    Purchase.query
                    .filter(Purchase.raffle_id == raffle.id)
                    .join(Purchase.tickets)
                    .filter(Ticket.id == ticket.id)
                    .order_by(Purchase.created_at.desc())
                    .first()
                )
        except ValueError:
            ticket = None

    return render_template(
        "admin/tickets.html",
        raffle=raffle,
        ticket=ticket,
        purchase=purchase,
        query_num=query_num
    )


@admin_bp.route("/tickets/<int:ticket_id>/force-free", methods=["POST"])
@login_required
def ticket_force_free(ticket_id: int):
    raffle = get_active_raffle()
    ticket = Ticket.query.filter_by(id=ticket_id, raffle_id=raffle.id).first_or_404()

    purchase = (
        Purchase.query
        .filter(Purchase.raffle_id == raffle.id)
        .join(Purchase.tickets)
        .filter(Ticket.id == ticket.id)
        .order_by(Purchase.created_at.desc())
        .first()
    )

    if purchase and purchase.status == PurchaseStatus.PAID:
        flash("Este boleto pertenece a una compra PAGADA. No se puede liberar aquí.", "error")
        return redirect(url_for("admin.tickets_manage", q=ticket.number))

    try:
        with begin_clean():
            ticket.status = TicketStatus.FREE
            if purchase and purchase.status in (PurchaseStatus.PENDING, PurchaseStatus.APPROVED):
                purchase.status = PurchaseStatus.CANCELLED
                purchase.cancelled_at = datetime.utcnow()
    except Exception:
        db.session.rollback()
        flash("No se pudo liberar el boleto.", "error")
        return redirect(url_for("admin.tickets_manage", q=ticket.number))

    log_audit("TICKET_FORCE_FREE", "Ticket", ticket.id, {"ticket": ticket.number})
    flash(f"Boleto {ticket.number:02d} liberado.", "success")
    return redirect(url_for("admin.tickets_manage", q=ticket.number))


@admin_bp.route("/manual-purchase", methods=["GET", "POST"])
@login_required
def manual_purchase():
    raffle = get_active_raffle()
    form = ManualPurchaseForm()

    prefill_numbers = ""
    selected_numbers = []

    raw_prefill = (request.args.get("prefill", "") or "").strip()
    if raw_prefill:
        parts = [p.strip() for p in raw_prefill.split(",") if p.strip()]
        nums = []
        for p in parts:
            try:
                n = int(p)
                if 1 <= n <= 100:
                    nums.append(n)
            except ValueError:
                continue
        nums = sorted(set(nums))[:raffle.max_tickets_per_purchase]
        selected_numbers = nums
        prefill_numbers = ",".join(str(n) for n in nums)

    if request.method == "GET":
        return render_template(
            "admin/manual_purchase.html",
            raffle=raffle,
            form=form,
            prefill_numbers=prefill_numbers,
            selected_numbers=selected_numbers
        )

    if not form.validate_on_submit():
        flash("Revisa el formulario.", "error")
        return render_template(
            "admin/manual_purchase.html",
            raffle=raffle,
            form=form,
            prefill_numbers=prefill_numbers,
            selected_numbers=selected_numbers
        ), 400

    # parse hidden numbers (POST)
    raw = (form.ticket_numbers.data or "").strip()
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    try:
        numbers = sorted(set(int(p) for p in parts))
    except ValueError:
        flash("Selección inválida de boletos.", "error")
        return redirect(url_for("admin.tickets_manage"))

    if not numbers or len(numbers) > raffle.max_tickets_per_purchase:
        flash("Debes seleccionar 1 a 3 boletos desde Admin → Boletos.", "error")
        return redirect(url_for("admin.tickets_manage"))

    try:
        phone_e164 = form.normalized_phone()
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("admin.manual_purchase", prefill=",".join(str(n) for n in numbers)))

    buyer_name = form.buyer_name.data.strip()
    status = form.status.data  # APPROVED / PAID
    notes = (form.notes.data or "").strip()
    ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)

    try:
        with begin_clean():
            selected_tickets = (
                Ticket.query
                .filter(and_(Ticket.raffle_id == raffle.id, Ticket.number.in_(numbers)))
                .with_for_update()
                .all()
            )

            if len(selected_tickets) != len(numbers):
                raise ValueError("Uno o más boletos no existen.")

            for t in selected_tickets:
                if t.status != TicketStatus.FREE:
                    raise ValueError(f"El boleto {t.number:02d} no está libre.")

            folio = generate_folio()
            purchase = Purchase(
                raffle_id=raffle.id,
                folio=folio,
                buyer_name=buyer_name,
                buyer_phone_e164=phone_e164,
                status=PurchaseStatus.PAID if status == "PAID" else PurchaseStatus.APPROVED,
                ip_address=ip_address,
                notes=notes or None
            )
            db.session.add(purchase)
            db.session.flush()

            now = datetime.utcnow()
            if status == "PAID":
                purchase.paid_at = now
            else:
                purchase.approved_at = now

            for t in selected_tickets:
                t.status = TicketStatus.PAID if status == "PAID" else TicketStatus.RESERVED
                purchase.tickets.append(t)

    except ValueError as e:
        db.session.rollback()
        flash(str(e), "error")
        return redirect(url_for("admin.tickets_manage"))
    except Exception:
        db.session.rollback()
        flash("Error al registrar la venta.", "error")
        return redirect(url_for("admin.tickets_manage"))

    log_audit("MANUAL_PURCHASE_CREATED", "Purchase", purchase.id, {"folio": purchase.folio, "numbers": numbers, "status": status})
    flash("Venta registrada. Se creó un folio y se actualizaron los boletos.", "success")
    return redirect(url_for("admin.purchase_detail", purchase_id=purchase.id))


@admin_bp.route("/purchases")
@login_required
def purchases():
    raffle = get_active_raffle()
    status = request.args.get("status", "").strip().upper()

    q = Purchase.query.filter_by(raffle_id=raffle.id).order_by(Purchase.created_at.desc())
    if status in PurchaseStatus.__members__:
        q = q.filter_by(status=PurchaseStatus[status])

    items = q.all()
    return render_template("admin/purchases.html", raffle=raffle, items=items, status=status)


@admin_bp.route("/purchases/<int:purchase_id>", methods=["GET", "POST"])
@login_required
def purchase_detail(purchase_id: int):
    raffle = get_active_raffle()
    purchase = Purchase.query.filter_by(id=purchase_id, raffle_id=raffle.id).first_or_404()
    note_form = AdminNoteForm(obj=purchase)

    if request.method == "POST":
        if note_form.validate_on_submit():
            purchase.notes = (note_form.notes.data or "").strip()
            db.session.commit()
            log_audit("PURCHASE_NOTE_UPDATED", "Purchase", purchase.id, {"folio": purchase.folio})
            flash("Notas guardadas.", "success")
        else:
            flash("Notas inválidas.", "error")

    wa_link = None
    if purchase.status == PurchaseStatus.PAID:
        msg = build_whatsapp_paid_message(
            buyer_name=purchase.buyer_name,
            folio=purchase.folio,
            ticket_numbers=[t.number for t in purchase.tickets],
            total_mxn=purchase.total_amount_mxn(),
        )
        wa_link = build_wa_link(purchase.buyer_phone_e164, msg)

    return render_template("admin/purchase_detail.html", raffle=raffle, purchase=purchase, wa_link=wa_link, note_form=note_form)


@admin_bp.route("/purchases/<int:purchase_id>/approve", methods=["POST"])
@login_required
def purchase_approve(purchase_id: int):
    raffle = get_active_raffle()
    purchase = Purchase.query.filter_by(id=purchase_id, raffle_id=raffle.id).first_or_404()

    if purchase.status != PurchaseStatus.PENDING:
        flash("Solo puedes aprobar solicitudes PENDIENTES.", "error")
        return redirect(url_for("admin.purchase_detail", purchase_id=purchase.id))

    purchase.status = PurchaseStatus.APPROVED
    purchase.approved_at = datetime.utcnow()
    db.session.commit()

    log_audit("PURCHASE_APPROVED", "Purchase", purchase.id, {"folio": purchase.folio})
    flash("Solicitud aprobada (Apartado).", "success")
    return redirect(url_for("admin.purchase_detail", purchase_id=purchase.id))


@admin_bp.route("/purchases/<int:purchase_id>/mark-paid", methods=["POST"])
@login_required
def purchase_mark_paid(purchase_id: int):
    raffle = get_active_raffle()
    purchase = Purchase.query.filter_by(id=purchase_id, raffle_id=raffle.id).first_or_404()

    if purchase.status not in (PurchaseStatus.PENDING, PurchaseStatus.APPROVED):
        flash("Solo puedes marcar como pagado una solicitud pendiente o aprobada.", "error")
        return redirect(url_for("admin.purchase_detail", purchase_id=purchase.id))

    try:
        with begin_clean():
            for t in purchase.tickets:
                t.status = TicketStatus.PAID
            purchase.status = PurchaseStatus.PAID
            purchase.paid_at = datetime.utcnow()
    except Exception:
        db.session.rollback()
        flash("No se pudo marcar como pagado.", "error")
        return redirect(url_for("admin.purchase_detail", purchase_id=purchase.id))

    log_audit("PURCHASE_MARK_PAID", "Purchase", purchase.id, {"folio": purchase.folio})
    flash("Compra marcada como PAGADA. Ya puedes enviar WhatsApp (1 click).", "success")
    return redirect(url_for("admin.purchase_detail", purchase_id=purchase.id))


@admin_bp.route("/purchases/<int:purchase_id>/cancel", methods=["POST"])
@login_required
def purchase_cancel(purchase_id: int):
    raffle = get_active_raffle()
    purchase = Purchase.query.filter_by(id=purchase_id, raffle_id=raffle.id).first_or_404()

    if purchase.status == PurchaseStatus.PAID:
        flash("No puedes cancelar una compra pagada desde aquí (por integridad).", "error")
        return redirect(url_for("admin.purchase_detail", purchase_id=purchase.id))

    try:
        with begin_clean():
            for t in purchase.tickets:
                t.status = TicketStatus.FREE
            purchase.status = PurchaseStatus.CANCELLED
            purchase.cancelled_at = datetime.utcnow()
    except Exception:
        db.session.rollback()
        flash("No se pudo cancelar.", "error")
        return redirect(url_for("admin.purchase_detail", purchase_id=purchase.id))

    log_audit("PURCHASE_CANCELLED", "Purchase", purchase.id, {"folio": purchase.folio})
    flash("Solicitud cancelada y boletos liberados.", "success")
    return redirect(url_for("admin.purchases"))


@admin_bp.route("/admins", methods=["GET", "POST"])
@login_required
def admin_users():
    form = AdminCreateUserForm()
    users = AdminUser.query.order_by(AdminUser.created_at.desc()).all()

    if request.method == "POST":
        if not form.validate_on_submit():
            flash("Revisa el formulario.", "error")
            return render_template("admin/admin_users.html", form=form, users=users), 400

        username = form.username.data.strip()
        temp_pw = form.temp_password.data

        ok, msg = validate_password_policy(temp_pw)
        if not ok:
            flash(msg, "error")
            return render_template("admin/admin_users.html", form=form, users=users), 400

        if AdminUser.query.filter_by(username=username).first():
            flash("Ese usuario ya existe.", "error")
            return render_template("admin/admin_users.html", form=form, users=users), 409

        new_u = AdminUser(username=username, must_change_password=True, is_active=True)
        new_u.set_password(temp_pw)
        db.session.add(new_u)
        db.session.commit()

        log_audit("ADMIN_CREATED", "AdminUser", new_u.id, {"username": username})
        flash("Admin creado. Debe cambiar contraseña al primer login.", "success")
        return redirect(url_for("admin.admin_users"))

    return render_template("admin/admin_users.html", form=form, users=users)


@admin_bp.route("/winners", methods=["GET", "POST"])
@login_required
def winners():
    raffle = get_active_raffle()
    form = WinnerForm()

    winners_row = Winners.query.filter_by(raffle_id=raffle.id).first()
    if not winners_row:
        winners_row = Winners(raffle_id=raffle.id)
        db.session.add(winners_row)
        db.session.commit()

    if request.method == "POST":
        if not form.validate_on_submit():
            flash("Completa los 3 números.", "error")
            return render_template("admin/winners.html", raffle=raffle, form=form, winners=winners_row), 400

        nums = [form.first_ticket.data, form.second_ticket.data, form.third_ticket.data]
        if any(n < 1 or n > 100 for n in nums):
            flash("Los ganadores deben estar entre 01 y 100.", "error")
            return render_template("admin/winners.html", raffle=raffle, form=form, winners=winners_row), 400
        if len(set(nums)) != 3:
            flash("Los 3 ganadores deben ser distintos.", "error")
            return render_template("admin/winners.html", raffle=raffle, form=form, winners=winners_row), 400

        winners_row.first_ticket = nums[0]
        winners_row.second_ticket = nums[1]
        winners_row.third_ticket = nums[2]
        winners_row.published_at = datetime.utcnow()
        db.session.commit()

        log_audit("WINNERS_PUBLISHED", "Winners", winners_row.id, {"nums": nums})
        flash("Ganadores publicados.", "success")
        return redirect(url_for("admin.winners"))

    if winners_row.first_ticket and request.method == "GET":
        form.first_ticket.data = winners_row.first_ticket
        form.second_ticket.data = winners_row.second_ticket
        form.third_ticket.data = winners_row.third_ticket

    return render_template("admin/winners.html", raffle=raffle, form=form, winners=winners_row)


@admin_bp.route("/audit")
@login_required
def audit():
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(300).all()
    return render_template("admin/audit.html", logs=logs)


@admin_bp.route("/reports")
@login_required
def reports():
    raffle = get_active_raffle()
    paid_tickets = Ticket.query.filter_by(raffle_id=raffle.id, status=TicketStatus.PAID).count()
    reserved_tickets = Ticket.query.filter_by(raffle_id=raffle.id, status=TicketStatus.RESERVED).count()
    free_tickets = Ticket.query.filter_by(raffle_id=raffle.id, status=TicketStatus.FREE).count()

    total_sold_mxn = paid_tickets * raffle.ticket_price_mxn

    paid_purchases = Purchase.query.filter_by(raffle_id=raffle.id, status=PurchaseStatus.PAID).count()
    pending_purchases = Purchase.query.filter_by(raffle_id=raffle.id, status=PurchaseStatus.PENDING).count()

    return render_template(
        "admin/reports.html",
        raffle=raffle,
        paid_tickets=paid_tickets,
        reserved_tickets=reserved_tickets,
        free_tickets=free_tickets,
        total_sold_mxn=total_sold_mxn,
        paid_purchases=paid_purchases,
        pending_purchases=pending_purchases
    )


@admin_bp.route("/reports/export.xlsx")
@login_required
def export_excel():
    raffle = get_active_raffle()
    purchases = Purchase.query.filter_by(raffle_id=raffle.id).order_by(Purchase.created_at.desc()).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Compras"

    ws.append(["Folio", "Nombre", "WhatsApp", "Estado", "Boletos", "Total MXN", "Creado", "Pagado", "Notas"])

    for p in purchases:
        nums = ", ".join([f"{t.number:02d}" for t in sorted(p.tickets, key=lambda x: x.number)])
        ws.append([
            p.folio,
            p.buyer_name,
            f"+{p.buyer_phone_e164}",
            p.status.value,
            nums,
            p.total_amount_mxn(),
            p.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            p.paid_at.strftime("%Y-%m-%d %H:%M:%S") if p.paid_at else "",
            (p.notes or "")[:500],
        ])

    out = BytesIO()
    wb.save(out)
    out.seek(0)

    log_audit("REPORT_EXCEL", "Raffle", raffle.id, {})
    return send_file(out, as_attachment=True, download_name="reporte_compras.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@admin_bp.route("/reports/export.pdf")
@login_required
def export_pdf():
    raffle = get_active_raffle()
    purchases = Purchase.query.filter_by(raffle_id=raffle.id).order_by(Purchase.created_at.desc()).all()

    out = BytesIO()
    c = canvas.Canvas(out, pagesize=letter)

    y = letter[1] - 40
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, y, f"Reporte de Compras - {raffle.name}")
    y -= 18
    c.setFont("Helvetica", 10)
    c.drawString(40, y, f"Generado: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    y -= 22

    c.setFont("Helvetica-Bold", 9)
    c.drawString(40, y, "Folio")
    c.drawString(120, y, "Nombre")
    c.drawString(280, y, "Estado")
    c.drawString(350, y, "Boletos")
    c.drawString(470, y, "Total")
    y -= 14
    c.setFont("Helvetica", 8)

    for p in purchases:
        if y < 60:
            c.showPage()
            y = letter[1] - 40
            c.setFont("Helvetica-Bold", 9)
            c.drawString(40, y, "Folio")
            c.drawString(120, y, "Nombre")
            c.drawString(280, y, "Estado")
            c.drawString(350, y, "Boletos")
            c.drawString(470, y, "Total")
            y -= 14
            c.setFont("Helvetica", 8)

        nums = ", ".join([f"{t.number:02d}" for t in sorted(p.tickets, key=lambda x: x.number)])
        c.drawString(40, y, p.folio)
        c.drawString(120, y, p.buyer_name[:24])
        c.drawString(280, y, p.status.value)
        c.drawString(350, y, nums[:18] + ("…" if len(nums) > 18 else ""))
        c.drawRightString(520, y, f"${p.total_amount_mxn()} MXN")
        y -= 12

    c.save()
    out.seek(0)

    log_audit("REPORT_PDF", "Raffle", raffle.id, {})
    return send_file(out, as_attachment=True, download_name="reporte_compras.pdf", mimetype="application/pdf")