import os

from app import create_app

app = create_app()


def _bootstrap_db_if_needed() -> None:
    """
    Render Free no permite Shell ni Pre-Deploy.
    Bootstrapping automático:
      - Si NO existe 'raffles' => corre alembic upgrade (flask-migrate)
      - Si NO hay rifa activa => corre seed usando Click main() (con contexto)
    Usa advisory lock para que sólo 1 worker haga esto.
    """
    if os.getenv("AUTO_BOOTSTRAP_DB", "1") != "1":
        return

    from app.extensions import db
    from sqlalchemy import text

    with app.app_context():
        lock_key = 987654321

        raw = None
        cur = None
        try:
            raw = db.engine.raw_connection()
            cur = raw.cursor()
            cur.execute("select pg_advisory_lock(%s)", (lock_key,))
            raw.commit()

            # 1) ¿Existe la tabla raffles?
            exists = None
            try:
                exists = db.session.execute(text("select to_regclass('public.raffles')")).scalar()
            except Exception:
                exists = None

            # 2) Si no existe, corre migraciones (crea tablas)
            if not exists:
                from flask_migrate import upgrade
                upgrade()

            # 3) Si no hay rifa activa, corre seed (con click context)
            raffle = None
            try:
                from app.models import Raffle
                raffle = Raffle.query.filter_by(is_active=True).first()
            except Exception:
                raffle = None

            if not raffle:
                # Importa el comando click ya registrado por Flask
                from app.cli import seed as seed_cmd

                # Ejecuta el comando como si fuera CLI, para que haya click context
                # standalone_mode=False evita sys.exit()
                seed_cmd.main(args=[], prog_name="seed", standalone_mode=False)

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


_bootstrap_db_if_needed()