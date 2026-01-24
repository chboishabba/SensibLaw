#!/usr/bin/env bash
set -euo pipefail

# Apply Postgres migrations in order. Configure connection via standard
# PG* environment variables or a DATABASE_URL (psql connection string).

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MIGRATIONS_DIR="${ROOT_DIR}/database/postgres_migrations"

if ! command -v psql >/dev/null 2>&1; then
    echo "psql is required to apply migrations but was not found on PATH." >&2
    exit 1
fi

if [[ ! -d "${MIGRATIONS_DIR}" ]]; then
    echo "Migration directory not found: ${MIGRATIONS_DIR}" >&2
    exit 1
fi

PSQL_CMD=("psql")
if [[ -n "${DATABASE_URL:-}" ]]; then
    PSQL_CMD+=("${DATABASE_URL}")
fi

for path in "${MIGRATIONS_DIR}"/*.sql; do
    echo "Applying $(basename "${path}")"
    "${PSQL_CMD[@]}" -v ON_ERROR_STOP=1 -f "${path}"
done
