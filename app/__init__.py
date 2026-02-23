import os
from flask import Flask
from dotenv import load_dotenv

from app.config import Config
from app.extensions import db, migrate, csrf, login_manager, limiter
from app.security import apply_security_headers
from app.public.routes import public_bp
from app.admin.routes import admin_bp
from app.models import AdminUser
from app.cli import register_cli


def create_app() -> Flask:
    load_dotenv()

    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(Config())

    # Extensions
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    login_manager.init_app(app)
    limiter.init_app(app)

    # Blueprints
    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp)

    # CLI
    register_cli(app)

    # Security headers
    app.after_request(apply_security_headers)

    # Login manager
    @login_manager.user_loader
    def load_user(user_id: str):
        return AdminUser.query.get(int(user_id))

    @app.errorhandler(404)
    def not_found(_):
        return ("Página no encontrada.", 404)

    @app.errorhandler(429)
    def too_many_requests(_):
        return ("Demasiadas solicitudes. Intenta más tarde.", 429)

    return app