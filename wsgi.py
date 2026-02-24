import os

from app import create_app

app = create_app()


def _bootstrap_db_if_needed() -> None:
    """
    Render Free no permite Shell ni Pre-Deploy.
    Entonces hacemos bootstrap automático:
      - Si NO existe la tabla 'raffles' => corre alembic upgrade (flask-migrate)
      - Si NO hay rifa activa => corre seed (tu comando existente)
    Esto solo corre una vez por deploy (bloqueo advisory en Postgres).
    """

    # Permite desactivarlo si algún día quieres:
    # AUTO_BOOTSTRAP_DB=0
    if os.getenv("AUTO_BOOTSTRAP_DB", "1") != "1":
        return

    from app.extensions import db
    from sqlalchemy import text

    with app.app_context():
        # Bloqueo global para evitar que varios workers intenten seed/migrate al mismo tiempo
        lock_key = 987654321

        raw = None
        cur = None
        try:
            raw = db.engine.raw_connection()
            cur = raw.cursor()
            cur.execute("select pg_advisory_lock(%s)", (lock_key,))
            raw.commit()

            # 1) ¿Existe la tabla raffles?
            try:
                exists = db.session.execute(text("select to_regclass('public.raffles')")).scalar()
            except Exception:
                exists = None

            # 2) Si no existe, corre migraciones (crea tablas)
            if not exists:
                from flask_migrate import upgrade
                upgrade()

            # 3) Si no hay rifa activa, corre seed (crea rifa + boletos + admin)
            try:
                from app.models import Raffle
                raffle = Raffle.query.filter_by(is_active=True).first()
            except Exception:
                raffle = None

            if not raffle:
                # Tu comando seed ya existe en app/cli.py
                from app.cli import seed as seed_cmd

                callback = getattr(seed_cmd, "callback", None)
                if callable(callback):
                    callback()
                else:
                    # Por si seed no es click.Command
                    seed_cmd()

        finally:
            # libera el lock
            try:
                if cur is not None:
                    cur.execute("select pg_advisory_unlock(%s)", (lock_key,))
                if raw is not None:
                    raw.commit()
            except Exception:
                pass

            try:
                if cur is not None:
                    cur.close()
            except Exception:
                pass

            try:
                if raw is not None:
                    raw.close()
            except Exception:
                pass


# Bootstrap al arrancar
_bootstrap_db_if_needed()