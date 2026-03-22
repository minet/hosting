#!/bin/sh
# Wait until the PowerDNS 'domains' table exists in PostgreSQL.
# This ensures the backend has finished running Alembic migrations
# before PowerDNS tries to query its tables.

PGHOST="${GPGSQL_HOST:-postgres}"
PGPORT="${GPGSQL_PORT:-5432}"
PGDATABASE="${GPGSQL_DBNAME:-hosting}"
PGUSER="${GPGSQL_USER:-app}"
export PGPASSWORD="${GPGSQL_PASSWORD:-app}"

echo "Waiting for PowerDNS schema (domains table) in ${PGHOST}:${PGPORT}/${PGDATABASE}..."

until psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -tAc \
  "SELECT 1 FROM information_schema.tables WHERE table_name='domains'" 2>/dev/null | grep -q 1; do
  echo "Schema not ready yet — retrying in 3s..."
  sleep 3
done

echo "PowerDNS schema is ready."
exec "$@"
