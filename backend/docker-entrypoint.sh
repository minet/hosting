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

alembic upgrade head
# Single worker required: _active_terminals in console.py is process-local.
# Do NOT add --workers >1 without switching to a shared store (Redis).
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips="${TRUSTED_PROXY_IPS:-127.0.0.1}" "$@"
