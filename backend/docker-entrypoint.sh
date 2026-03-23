#!/bin/sh
set -e

python - <<'EOF'
from sqlalchemy import text
from app.core.config import get_settings
from app.db.core.engine import init_db, get_engine
import subprocess

init_db(get_settings())
engine = get_engine()
with engine.connect() as conn:
    has_version = conn.execute(text("SELECT to_regclass('public.alembic_version')")).scalar()
    has_tables  = conn.execute(text("SELECT to_regclass('public.templates')")).scalar()

if has_version is None and has_tables is not None:
    print("Legacy schema detected — stamping Alembic revision to 0001", flush=True)
    subprocess.run(["alembic", "stamp", "0001"], check=True)
EOF

alembic upgrade head
# Single worker required: _active_terminals in console.py is process-local.
# Do NOT add --workers >1 without switching to a shared store (Redis).
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*' "$@"
