#!/bin/sh
set -e

python - <<'EOF'
from sqlalchemy import create_engine, text
from app.core.config import get_settings
import subprocess

settings = get_settings()
# Use a sync engine for this one-shot migration check — the async engine
# cannot be used in a plain (non-asyncio) script context.
engine = create_engine(settings.database_url)
with engine.connect() as conn:
    has_version = conn.execute(text("SELECT to_regclass('public.alembic_version')")).scalar()
    has_tables  = conn.execute(text("SELECT to_regclass('public.templates')")).scalar()
engine.dispose()

if has_version is None and has_tables is not None:
    print("Legacy schema detected — stamping Alembic revision to 0001", flush=True)
    subprocess.run(["alembic", "stamp", "0001"], check=True)
EOF

alembic upgrade head
# Single worker required: _active_terminals in console.py is process-local.
# Do NOT add --workers >1 without switching to a shared store (Redis).
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*' "$@"
