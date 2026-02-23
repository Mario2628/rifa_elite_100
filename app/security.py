import re
from datetime import datetime, timedelta
from typing import Tuple
from flask import current_app, request


PHONE_RE = re.compile(r"^\+?\d{10,15}$")


def normalize_mx_phone(raw: str) -> str:
    """
    Normaliza a formato dígitos E.164 SIN '+'.
    Acepta:
      - 10 dígitos (MX) -> '52' + 10 dígitos
      - 12 dígitos iniciando con 52 -> se deja igual
      - Con '+' opcional
    Devuelve: '52XXXXXXXXXX'
    Lanza ValueError si no es válido.
    """
    if not raw:
        raise ValueError("Teléfono vacío")

    digits = re.sub(r"\D", "", raw)
    if len(digits) == 10:
        return "52" + digits
    if len(digits) == 12 and digits.startswith("52"):
        return digits

    # Aceptar otros largos si fueran E164 válidos, pero en este proyecto usamos MX
    raise ValueError("Teléfono inválido. Usa 10 dígitos (MX) o 52 + 10 dígitos.")


def format_phone_plus(phone_e164_digits: str) -> str:
    if not phone_e164_digits:
        return ""
    return f"+{phone_e164_digits}"


def validate_password_policy(pw: str) -> Tuple[bool, str]:
    """
    Política: 12+ chars, 1 mayúscula, 1 minúscula, 1 dígito, 1 símbolo.
    """
    if not pw or len(pw) < 12:
        return False, "La contraseña debe tener al menos 12 caracteres."
    if not re.search(r"[A-Z]", pw):
        return False, "La contraseña debe incluir al menos 1 letra mayúscula."
    if not re.search(r"[a-z]", pw):
        return False, "La contraseña debe incluir al menos 1 letra minúscula."
    if not re.search(r"\d", pw):
        return False, "La contraseña debe incluir al menos 1 número."
    if not re.search(r"[^A-Za-z0-9]", pw):
        return False, "La contraseña debe incluir al menos 1 símbolo."
    return True, "OK"


def apply_security_headers(response):
    """
    Encabezados de seguridad fuertes (sin librerías externas).
    CSP sin CDNs (todo local).
    """
    csp = (
        "default-src 'self'; "
        "img-src 'self' data:; "
        "style-src 'self'; "
        "script-src 'self'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none'; "
        "object-src 'none';"
    )

    response.headers["Content-Security-Policy"] = csp
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"

    # HSTS solo si estás en HTTPS (Render sí). En local no.
    if request.is_secure:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    return response