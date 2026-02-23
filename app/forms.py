from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, HiddenField, BooleanField, IntegerField,
    TextAreaField, SelectField
)
from wtforms.validators import DataRequired, Length, Optional

from app.security import normalize_mx_phone


class TicketRequestForm(FlaskForm):
    buyer_name = StringField("Nombre", validators=[DataRequired(), Length(min=2, max=120)])
    buyer_phone = StringField("WhatsApp", validators=[DataRequired(), Length(min=10, max=20)])
    ticket_numbers = HiddenField("Boletos", validators=[DataRequired()])
    confirm_age = BooleanField("Confirmo que soy mayor de 18 años", validators=[DataRequired()])
    accept_terms = BooleanField("Acepto términos y aviso de privacidad", validators=[DataRequired()])

    def normalized_phone(self) -> str:
        return normalize_mx_phone(self.buyer_phone.data)


class VerifyForm(FlaskForm):
    folio = StringField("Folio", validators=[DataRequired(), Length(min=4, max=32)])
    phone = StringField("WhatsApp", validators=[DataRequired(), Length(min=10, max=20)])

    def normalized_phone(self) -> str:
        return normalize_mx_phone(self.phone.data)


class AdminLoginForm(FlaskForm):
    username = StringField("Usuario", validators=[DataRequired(), Length(min=2, max=80)])
    password = PasswordField("Contraseña", validators=[DataRequired(), Length(min=1, max=255)])


class AdminChangePasswordForm(FlaskForm):
    current_password = PasswordField("Contraseña actual", validators=[DataRequired()])
    new_password = PasswordField("Nueva contraseña", validators=[DataRequired()])
    confirm_password = PasswordField("Confirmar nueva contraseña", validators=[DataRequired()])


class AdminCreateUserForm(FlaskForm):
    username = StringField("Usuario", validators=[DataRequired(), Length(min=2, max=80)])
    temp_password = PasswordField("Contraseña temporal", validators=[DataRequired(), Length(min=12, max=255)])


class WinnerForm(FlaskForm):
    first_ticket = IntegerField("1er lugar (01-100)", validators=[DataRequired()])
    second_ticket = IntegerField("2do lugar (01-100)", validators=[DataRequired()])
    third_ticket = IntegerField("3er lugar (01-100)", validators=[DataRequired()])


class AdminNoteForm(FlaskForm):
    notes = TextAreaField("Notas internas", validators=[Length(max=2000)])


class ManualPurchaseForm(FlaskForm):
    buyer_name = StringField("Nombre", validators=[DataRequired(), Length(min=2, max=120)])
    buyer_phone = StringField("WhatsApp", validators=[DataRequired(), Length(min=10, max=20)])

    # ✅ ahora lo llena el GRID (hidden) y NO se escribe a mano
    ticket_numbers = HiddenField("Boletos", validators=[DataRequired()])

    status = SelectField(
        "Estado",
        choices=[("APPROVED", "Apartado"), ("PAID", "Pagado")],
        validators=[DataRequired()]
    )
    notes = TextAreaField("Notas internas", validators=[Optional(), Length(max=2000)])

    def normalized_phone(self) -> str:
        return normalize_mx_phone(self.buyer_phone.data)