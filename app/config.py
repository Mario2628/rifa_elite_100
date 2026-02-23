import os


class Config:
    def __init__(self) -> None:
        self.SECRET_KEY = os.getenv("SECRET_KEY", "CHANGE_ME")

        # DB
        self.SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
        if not self.SQLALCHEMY_DATABASE_URI:
            raise RuntimeError("DATABASE_URL no está configurado en .env")
        self.SQLALCHEMY_TRACK_MODIFICATIONS = False

        # Cookies
        self.SESSION_COOKIE_HTTPONLY = True
        self.SESSION_COOKIE_SAMESITE = "Lax"
        self.REMEMBER_COOKIE_HTTPONLY = True
        self.REMEMBER_COOKIE_SAMESITE = "Lax"

        self.SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "0") == "1"
        self.REMEMBER_COOKIE_SECURE = os.getenv("REMEMBER_COOKIE_SECURE", "0") == "1"

        # CSRF
        self.WTF_CSRF_TIME_LIMIT = 60 * 60  # 1h

        # Limiter
        self.RATELIMIT_DEFAULT = "200 per hour"

        # App settings
        self.APP_NAME = os.getenv("APP_NAME", "Rifa Élite 100")
        self.ORGANIZER_NAME = os.getenv("ORGANIZER_NAME", "")
        self.ORGANIZER_LOCATION = os.getenv("ORGANIZER_LOCATION", "")
        self.WHATSAPP_PHONE_E164 = os.getenv("WHATSAPP_PHONE_E164", "52XXXXXXXXXX")

        try:
            self.TICKET_PRICE_MXN = int(os.getenv("TICKET_PRICE_MXN", "150"))
        except ValueError:
            self.TICKET_PRICE_MXN = 150

        try:
            self.MAX_TICKETS_PER_PURCHASE = int(os.getenv("MAX_TICKETS_PER_PURCHASE", "3"))
        except ValueError:
            self.MAX_TICKETS_PER_PURCHASE = 3

        self.DRAW_AT_LOCAL = os.getenv("DRAW_AT_LOCAL", "2026-03-06 20:00:00")