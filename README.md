# Rifa Élite 100 (Flask + PostgreSQL)

## Requisitos
- Python 3.10+
- PostgreSQL 14+

## Instalación
1) Crear venv y activar
2) `pip install -r requirements.txt`
3) Crear DB en PostgreSQL
4) Copiar `.env.example` a `.env` y editar
5) Migraciones:
   - `flask db init`
   - `flask db migrate -m "init"`
   - `flask db upgrade`
6) Seed:
   - `flask seed`
7) Ejecutar:
   - `flask run`

## Admin
- /admin
- Usuario inicial: Mendez
- Contraseña temporal: la que pusiste en `.env`
- Se fuerza cambio de contraseña al primer login.