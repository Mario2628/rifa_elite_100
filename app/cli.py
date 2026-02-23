import os
from datetime import datetime

from flask import current_app
from flask.cli import with_appcontext
import click

from app.extensions import db
from app.models import Raffle, Ticket, TicketStatus, AdminUser, Winners


@click.command("seed")
@with_appcontext
def seed():
    """
    Crea:
      - rifa activa
      - tickets 01..100
      - winners row vacío
      - admin inicial (Mendez) con contraseña temporal
    """
    app_name = current_app.config.get("APP_NAME", "Rifa Élite 100")
    organizer_name = current_app.config.get("ORGANIZER_NAME", "")
    organizer_location = current_app.config.get("ORGANIZER_LOCATION", "")
    whatsapp = current_app.config.get("WHATSAPP_PHONE_E164", "52XXXXXXXXXX")
    price = current_app.config.get("TICKET_PRICE_MXN", 150)
    max_t = current_app.config.get("MAX_TICKETS_PER_PURCHASE", 3)

    draw_str = current_app.config.get("DRAW_AT_LOCAL", "2026-03-06 20:00:00")
    draw_at = datetime.strptime(draw_str, "%Y-%m-%d %H:%M:%S")

    # Admin seed vars
    initial_user = os.getenv("INITIAL_ADMIN_USERNAME", "Mendez")
    initial_pw = os.getenv("INITIAL_ADMIN_TEMP_PASSWORD", "")

    if not initial_pw or len(initial_pw) < 12:
        raise click.ClickException("INITIAL_ADMIN_TEMP_PASSWORD inválida. Configúrala en .env (12+).")

    raffle = Raffle.query.filter_by(is_active=True).first()
    if not raffle:
        raffle = Raffle(
            name=app_name,
            organizer_name=organizer_name,
            organizer_location=organizer_location,
            whatsapp_phone_e164=whatsapp,
            ticket_price_mxn=price,
            max_tickets_per_purchase=max_t,
            draw_at_local=draw_at,
            is_active=True,
        )
        db.session.add(raffle)
        db.session.commit()
        click.echo(f"✅ Rifa creada: {raffle.name}")
    else:
        click.echo(f"ℹ️ Ya existe rifa activa: {raffle.name}")

    # Tickets
    existing = Ticket.query.filter_by(raffle_id=raffle.id).count()
    if existing < 100:
        for n in range(1, 101):
            if not Ticket.query.filter_by(raffle_id=raffle.id, number=n).first():
                db.session.add(Ticket(raffle_id=raffle.id, number=n, status=TicketStatus.FREE))
        db.session.commit()
        click.echo("✅ Tickets 01-100 listos.")
    else:
        click.echo("ℹ️ Tickets ya existen.")

    # Winners row
    if not Winners.query.filter_by(raffle_id=raffle.id).first():
        db.session.add(Winners(raffle_id=raffle.id))
        db.session.commit()
        click.echo("✅ Winners row creado.")
    else:
        click.echo("ℹ️ Winners row ya existe.")

    # Admin user
    admin = AdminUser.query.filter_by(username=initial_user).first()
    if not admin:
        admin = AdminUser(username=initial_user, must_change_password=True, is_active=True)
        admin.set_password(initial_pw)
        db.session.add(admin)
        db.session.commit()
        click.echo(f"✅ Admin creado: {initial_user} (debe cambiar contraseña al entrar)")
    else:
        click.echo("ℹ️ Admin inicial ya existe.")


def register_cli(app):
    app.cli.add_command(seed)