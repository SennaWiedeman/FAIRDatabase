#!/bin/bash
set -e

# Source .env if it exists and was bind-mounted (dev convenience).
# In production, environment variables come from docker-compose environment/env_file.
if [ -f /app/backend/.env ]; then
    set -a
    source /app/backend/.env
    set +a
fi

# Apply schema migrations idempotently before launching Flask. Both files use
# IF NOT EXISTS / ON CONFLICT DO NOTHING, so re-running on every boot is safe.
# This covers existing volumes that pre-date the docker-entrypoint-initdb.d mounts.
if [ -n "${POSTGRES_HOST:-}" ] && [ -n "${POSTGRES_SECRET:-}" ]; then
    echo "[entrypoint] applying schema migrations..."
    for sql in /app/backend/migrate_schema.sql /app/backend/pbpk_schema.sql; do
        if [ -f "$sql" ]; then
            PGPASSWORD="$POSTGRES_SECRET" psql \
                -h "$POSTGRES_HOST" -p "${POSTGRES_PORT:-5432}" \
                -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB_NAME:-postgres}" \
                -v ON_ERROR_STOP=0 -f "$sql" \
                && echo "[entrypoint] applied $sql" \
                || echo "[entrypoint] WARNING: failed to apply $sql (continuing)"
        fi
    done
fi

exec "$@"
