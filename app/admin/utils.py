import urllib.parse
from datetime import datetime

from flask import current_app

from app.security import format_phone_plus


def build_whatsapp_paid_message(buyer_name: str, folio: str, ticket_numbers, total_mxn: int) -> str:
    draw_at = current_app.config.get("DRAW_AT_LOCAL", "2026-03-06 20:00:00")
    app_name = current_app.config.get("APP_NAME", "Rifa Élite 100")

    nums = ", ".join([f"{n:02d}" for n in sorted(ticket_numbers)])

    msg = (
        f"✅ PAGO CONFIRMADO – {app_name}\n"
        f"Hola {buyer_name}, tu pago quedó registrado.\n"
        f"Folio: {folio}\n"
        f"Boletos: {nums}\n"
        f"Total pagado: ${total_mxn} MXN\n"
        f"Sorteo: 06/Mar/2026 – 8:00 PM (CDMX)\n\n"
        f"📌 Guarda este mensaje como comprobante.\n"
        f"🔄 Si cambiaste de número contáctanos para actualizar tus datos.\n"
        f"🔞 Participación exclusiva para mayores de 18 años."
    )
    return msg


def build_wa_link(phone_e164_digits: str, text: str) -> str:
    # wa.me necesita dígitos sin '+'
    encoded = urllib.parse.quote(text)
    return f"https://wa.me/{phone_e164_digits}?text={encoded}"