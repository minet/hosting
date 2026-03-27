#!/bin/sh
set -e

echo "Waiting for database..."
python -c "
import time, sys
from app.core.config import get_settings
from urllib.parse import urlparse

settings = get_settings()
url = settings.database_url
parsed = urlparse(url)
safe_url = url.replace(parsed.password, '***') if parsed.password else url
print(f'  Target: {safe_url}', flush=True)

from sqlalchemy import create_engine, text

for attempt in range(1, 31):
    try:
        engine = create_engine(url, connect_args={'connect_timeout': 5})
        with engine.connect() as c:
            c.execute(text('SELECT 1'))
        engine.dispose()
        print('Database is ready!', flush=True)
        break
    except Exception as e:
        if engine:
            engine.dispose()
        print(f'  Attempt {attempt}/30 — not ready yet: {e}', flush=True)
        time.sleep(2)
else:
    print('ERROR: Database not reachable after 30 attempts.', file=sys.stderr, flush=True)
    sys.exit(1)
"

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
