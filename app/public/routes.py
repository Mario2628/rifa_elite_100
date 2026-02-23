import json
from datetime import datetime

from flask import Blueprint, render_template, current_app, request, redirect, url_for, flash, jsonify
from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError

from app.extensions import db, limiter
from app.models import (
    Raffle, Ticket, TicketStatus, Purchase, PurchaseStatus, Winners, generate_folio
)
from app.forms import TicketRequestForm, VerifyForm

public_bp = Blueprint("public", __name__)


def begin_clean():
    """
    SQLAlchemy 2.x inicia una transacción automática (autobegin) en el primer SELECT.
    Si después llamas session.begin() puede fallar con:
      InvalidRequestError: A transaction is already begun on this Session.

    Solución: rollback para cerrar la transacción automática y luego begin controlado.
    """
    try:
        db.session.rollback()
    except Exception:
        pass
    return db.session.begin()


def get_active_raffle() -> Raffle:
    raffle = Raffle.query.filter_by(is_active=True).order_by(Raffle.id.desc()).first()
    if not raffle:
        raise RuntimeError("No hay rifa activa. Ejecuta 'flask seed'.")
    return raffle


@public_bp.route("/")
def home():
    raffle = get_active_raffle()
    total = Ticket.query.filter_by(raffle_id=raffle.id).count()
    free = Ticket.query.filter_by(raffle_id=raffle.id, status=TicketStatus.FREE).count()
    reserved = Ticket.query.filter_by(raffle_id=raffle.id, status=TicketStatus.RESERVED).count()
    paid = Ticket.query.filter_by(raffle_id=raffle.id, status=TicketStatus.PAID).count()

    winners = Winners.query.filter_by(raffle_id=raffle.id).first()

    return render_template(
        "public/home.html",
        raffle=raffle,
        total=total,
        free=free,
        reserved=reserved,
        paid=paid,
        winners=winners,
    )


@public_bp.route("/premios")
def prizes():
    raffle = get_active_raffle()
    return render_template("public/prizes.html", raffle=raffle)


@public_bp.route("/boletos")
def tickets():
    raffle = get_active_raffle()
    total = Ticket.query.filter_by(raffle_id=raffle.id).count()
    free = Ticket.query.filter_by(raffle_id=raffle.id, status=TicketStatus.FREE).count()
    reserved = Ticket.query.filter_by(raffle_id=raffle.id, status=TicketStatus.RESERVED).count()
    paid = Ticket.query.filter_by(raffle_id=raffle.id, status=TicketStatus.PAID).count()

    return render_template(
        "public/tickets.html",
        raffle=raffle,
        total=total,
        free=free,
        reserved=reserved,
        paid=paid,
    )


@public_bp.route("/api/tickets")
def api_tickets():
    raffle = get_active_raffle()
    tickets = Ticket.query.filter_by(raffle_id=raffle.id).order_by(Ticket.number.asc()).all()
    return jsonify({
        "raffle_id": raffle.id,
        "tickets": [{"n": t.number, "s": t.status.value} for t in tickets]
    })


@public_bp.route("/solicitar", methods=["GET", "POST"])
@limiter.limit("15 per hour")
def request_tickets():
    raffle = get_active_raffle()
    form = TicketRequestForm()

    if request.method == "GET":
        return render_template("public/request.html", raffle=raffle, form=form)

    if not form.validate_on_submit():
        flash("Revisa el formulario. Asegúrate de aceptar +18 y términos.", "error")
        return render_template("public/request.html", raffle=raffle, form=form), 400

    try:
        phone_e164 = form.normalized_phone()
    except ValueError as e:
        flash(str(e), "error")
        return render_template("public/request.html", raffle=raffle, form=form), 400

    raw_numbers = (form.ticket_numbers.data or "").strip()
    try:
        numbers = [int(x) for x in raw_numbers.split(",") if x.strip()]
    except ValueError:
        flash("Selección inválida de boletos.", "error")
        return render_template("public/request.html", raffle=raffle, form=form), 400

    numbers = sorted(set(numbers))
    if len(numbers) == 0:
        flash("Selecciona al menos 1 boleto.", "error")
        return render_template("public/request.html", raffle=raffle, form=form), 400

    if len(numbers) > raffle.max_tickets_per_purchase:
        flash(f"Máximo {raffle.max_tickets_per_purchase} boletos por compra.", "error")
        return render_template("public/request.html", raffle=raffle, form=form), 400

    if any(n < 1 or n > 100 for n in numbers):
        flash("Los boletos deben estar entre 01 y 100.", "error")
        return render_template("public/request.html", raffle=raffle, form=form), 400

    existing_pending = Purchase.query.filter_by(
        raffle_id=raffle.id,
        buyer_phone_e164=phone_e164,
        status=PurchaseStatus.PENDING
    ).first()
    if existing_pending:
        flash("Ya tienes una solicitud pendiente con este WhatsApp. Espera confirmación o contáctanos.", "error")
        return render_template("public/request.html", raffle=raffle, form=form), 409

    buyer_name = form.buyer_name.data.strip()
    ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)

    try:
        # ✅ FIX: evita InvalidRequestError por autobegin
        with begin_clean():
            selected_tickets = (
                Ticket.query
                .filter(and_(
                    Ticket.raffle_id == raffle.id,
                    Ticket.number.in_(numbers)
                ))
                .with_for_update()
                .all()
            )

            if len(selected_tickets) != len(numbers):
                raise ValueError("Uno o más boletos no existen.")

            for t in selected_tickets:
                if t.status != TicketStatus.FREE:
                    raise ValueError(f"El boleto {t.number:02d} ya no está libre.")

            folio = generate_folio()
            purchase = Purchase(
                raffle_id=raffle.id,
                folio=folio,
                buyer_name=buyer_name,
                buyer_phone_e164=phone_e164,
                status=PurchaseStatus.PENDING,
                ip_address=ip_address,
            )
            db.session.add(purchase)
            db.session.flush()

            for t in selected_tickets:
                t.status = TicketStatus.RESERVED
                purchase.tickets.append(t)

    except ValueError as e:
        db.session.rollback()
        flash(str(e), "error")
        return render_template("public/request.html", raffle=raffle, form=form), 409
    except IntegrityError:
        db.session.rollback()
        flash("Error al generar folio. Intenta de nuevo.", "error")
        return render_template("public/request.html", raffle=raffle, form=form), 500
    except Exception:
        db.session.rollback()
        flash("Error al procesar la solicitud.", "error")
        return render_template("public/request.html", raffle=raffle, form=form), 500

    return render_template(
        "public/request_success.html",
        raffle=raffle,
        purchase=purchase,
        selected_numbers=numbers
    )


@public_bp.route("/verificar", methods=["GET", "POST"])
def verify():
    raffle = get_active_raffle()
    form = VerifyForm()
    purchase = None

    if request.method == "POST":
        if not form.validate_on_submit():
            flash("Completa folio y WhatsApp.", "error")
            return render_template("public/verify.html", raffle=raffle, form=form, purchase=None), 400

        folio = form.folio.data.strip().upper()

        try:
            phone_e164 = form.normalized_phone()
        except ValueError as e:
            flash(str(e), "error")
            return render_template("public/verify.html", raffle=raffle, form=form, purchase=None), 400

        purchase = Purchase.query.filter_by(
            raffle_id=raffle.id,
            folio=folio,
            buyer_phone_e164=phone_e164
        ).first()

        if not purchase:
            flash("No se encontró la compra. Verifica folio y WhatsApp.", "error")

    return render_template("public/verify.html", raffle=raffle, form=form, purchase=purchase)


@public_bp.route("/como-pagar")
def how_to_pay():
    raffle = get_active_raffle()
    return render_template("public/how_to_pay.html", raffle=raffle)


@public_bp.route("/contacto")
def contact():
    raffle = get_active_raffle()
    return render_template("public/contact.html", raffle=raffle)


@public_bp.route("/terminos")
def terms():
    raffle = get_active_raffle()
    return render_template("public/terms.html", raffle=raffle)


@public_bp.route("/resultados")
def results():
    raffle = get_active_raffle()
    winners = Winners.query.filter_by(raffle_id=raffle.id).first()
    return render_template("public/results.html", raffle=raffle, winners=winners)