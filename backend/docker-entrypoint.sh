#!/bin/sh
set -e

echo "Waiting for database to be ready..."
MAX_RETRIES=30
RETRY=0
while [ "$RETRY" -lt "$MAX_RETRIES" ]; do
  python -c "
from sqlalchemy import create_engine, text
from app.core.config import get_settings
engine = create_engine(get_settings().database_url)
with engine.connect() as c: c.execute(text('SELECT 1'))
engine.dispose()
" 2>/dev/null && break
  RETRY=$((RETRY + 1))
  echo "Database not ready yet (attempt $RETRY/$MAX_RETRIES)..."
  sleep 2
done

if [ "$RETRY" -eq "$MAX_RETRIES" ]; then
  echo "ERROR: Could not connect to database after $MAX_RETRIES attempts"
  exit 1
fi
echo "Database is ready!"

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
