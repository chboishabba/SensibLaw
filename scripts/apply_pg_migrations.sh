#!/usr/bin/env bash
set -euo pipefail

# Apply PostgreSQL migrations in lexical order with immutable content hashes.
# Configure the connection through standard PG* variables or DATABASE_URL.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MIGRATIONS_DIR="${ROOT_DIR}/database/postgres_migrations"

if ! command -v psql >/dev/null 2>&1; then
    echo "psql is required to apply migrations but was not found on PATH." >&2
    exit 1
fi
if ! command -v sha256sum >/dev/null 2>&1; then
    echo "sha256sum is required to verify immutable migrations." >&2
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

"${PSQL_CMD[@]}" -v ON_ERROR_STOP=1 -c "
CREATE TABLE IF NOT EXISTS public.sensiblaw_schema_migration (
    migration_name text PRIMARY KEY,
    content_sha256 text NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now()
);"

for path in "${MIGRATIONS_DIR}"/*.sql; do
    name="$(basename "${path}")"
    digest="$(sha256sum "${path}" | awk '{print $1}')"
    existing="$(
        "${PSQL_CMD[@]}" -At -v ON_ERROR_STOP=1 \
            -c "SELECT content_sha256 FROM public.sensiblaw_schema_migration WHERE migration_name = '${name}'"
    )"
    if [[ -n "${existing}" ]]; then
        if [[ "${existing}" != "${digest}" ]]; then
            echo "Migration hash mismatch for ${name}: database=${existing} file=${digest}" >&2
            exit 1
        fi
        echo "Already applied ${name} (${digest})"
        continue
    fi
    echo "Applying ${name} (${digest})"
    "${PSQL_CMD[@]}" -v ON_ERROR_STOP=1 -f "${path}"
    "${PSQL_CMD[@]}" -v ON_ERROR_STOP=1 -c "
        INSERT INTO public.sensiblaw_schema_migration
            (migration_name, content_sha256)
        VALUES ('${name}', '${digest}');"
done
