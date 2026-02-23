import os
import secrets
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db


class TicketStatus(str, Enum):
    FREE = "FREE"
    RESERVED = "RESERVED"  # público: Apartado
    PAID = "PAID"


class PurchaseStatus(str, Enum):
    PENDING = "PENDING"      # solicitud enviada, pendiente admin
    APPROVED = "APPROVED"    # admin aprueba apartado
    PAID = "PAID"            # admin confirma pago
    CANCELLED = "CANCELLED"  # admin cancela solicitud / libera


class Raffle(db.Model):
    __tablename__ = "raffles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    organizer_name = db.Column(db.String(200), nullable=False)
    organizer_location = db.Column(db.String(200), nullable=False)
    whatsapp_phone_e164 = db.Column(db.String(20), nullable=False)

    ticket_price_mxn = db.Column(db.Integer, nullable=False, default=150)
    max_tickets_per_purchase = db.Column(db.Integer, nullable=False, default=3)

    draw_at_local = db.Column(db.DateTime, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    tickets = db.relationship("Ticket", backref="raffle", lazy=True)
    purchases = db.relationship("Purchase", backref="raffle", lazy=True)


class Ticket(db.Model):
    __tablename__ = "tickets"
    __table_args__ = (db.UniqueConstraint("raffle_id", "number", name="uq_ticket_number_per_raffle"),)

    id = db.Column(db.Integer, primary_key=True)
    raffle_id = db.Column(db.Integer, db.ForeignKey("raffles.id"), nullable=False)
    number = db.Column(db.Integer, nullable=False)  # 1..100
    status = db.Column(db.Enum(TicketStatus), nullable=False, default=TicketStatus.FREE)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


purchase_tickets = db.Table(
    "purchase_tickets",
    db.Column("purchase_id", db.Integer, db.ForeignKey("purchases.id"), primary_key=True),
    db.Column("ticket_id", db.Integer, db.ForeignKey("tickets.id"), primary_key=True),
)


class Purchase(db.Model):
    __tablename__ = "purchases"

    id = db.Column(db.Integer, primary_key=True)
    raffle_id = db.Column(db.Integer, db.ForeignKey("raffles.id"), nullable=False)

    folio = db.Column(db.String(32), unique=True, nullable=False, index=True)

    buyer_name = db.Column(db.String(120), nullable=False)
    buyer_phone_e164 = db.Column(db.String(20), nullable=False, index=True)

    status = db.Column(db.Enum(PurchaseStatus), nullable=False, default=PurchaseStatus.PENDING)

    ip_address = db.Column(db.String(45), nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    approved_at = db.Column(db.DateTime, nullable=True)
    paid_at = db.Column(db.DateTime, nullable=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)

    notes = db.Column(db.Text, nullable=True)

    tickets = db.relationship("Ticket", secondary=purchase_tickets, lazy="subquery")

    def total_amount_mxn(self) -> int:
        price = self.raffle.ticket_price_mxn
        return price * len(self.tickets)


class AdminUser(UserMixin, db.Model):
    __tablename__ = "admin_users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)

    password_hash = db.Column(db.String(255), nullable=False)
    must_change_password = db.Column(db.Boolean, nullable=False, default=True)

    is_active = db.Column(db.Boolean, nullable=False, default=True)

    failed_login_attempts = db.Column(db.Integer, nullable=False, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)
    last_login_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def is_locked(self) -> bool:
        return self.locked_until is not None and datetime.utcnow() < self.locked_until

    def register_failed_login(self) -> None:
        self.failed_login_attempts += 1
        # lockout progresivo
        if self.failed_login_attempts >= 5:
            self.locked_until = datetime.utcnow() + timedelta(minutes=15)

    def reset_login_failures(self) -> None:
        self.failed_login_attempts = 0
        self.locked_until = None


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    admin_user_id = db.Column(db.Integer, db.ForeignKey("admin_users.id"), nullable=True)

    action = db.Column(db.String(80), nullable=False)
    entity_type = db.Column(db.String(80), nullable=True)
    entity_id = db.Column(db.Integer, nullable=True)

    meta_json = db.Column(db.Text, nullable=True)  # JSON string (simple y portable)
    ip_address = db.Column(db.String(45), nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    admin_user = db.relationship("AdminUser", lazy=True)


class Winners(db.Model):
    __tablename__ = "winners"

    id = db.Column(db.Integer, primary_key=True)
    raffle_id = db.Column(db.Integer, db.ForeignKey("raffles.id"), nullable=False, unique=True)

    first_ticket = db.Column(db.Integer, nullable=True)
    second_ticket = db.Column(db.Integer, nullable=True)
    third_ticket = db.Column(db.Integer, nullable=True)

    published_at = db.Column(db.DateTime, nullable=True)

    raffle = db.relationship("Raffle", lazy=True)


def generate_folio() -> str:
    # RF26-XXXXXX
    token = secrets.token_hex(3).upper()  # 6 chars hex
    return f"RF26-{token}"