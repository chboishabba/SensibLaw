"""Provision and migrate a retained local PostgreSQL authority database."""

from __future__ import annotations

import hashlib
from pathlib import Path
import re
from uuid import uuid4

from src.runtime.strict_postgres_execution import StrictExecutionError


def _database_name(run_ref: str | None) -> str:
    """Return a readable but collision-resistant retained database name."""

    source = str(run_ref or "run")
    stem = re.sub(r"[^a-z0-9]+", "", source.lower())[:12] or "run"
    run_digest = hashlib.sha256(source.encode("utf-8")).hexdigest()[:8]
    nonce = uuid4().hex[:12]
    return f"sensiblaw_strict_{stem}{run_digest}{nonce}"


def provision_local_postgres(
    *,
    admin_url: str | None,
    migration_root: str | Path,
    run_ref: str | None = None,
) -> tuple[str, str]:
    """Create a uniquely named database, apply migrations, and retain it.

    The caller must provide a local/admin connection URL (normally
    ``DATABASE_URL`` or ``SENSIBLAW_LOCAL_POSTGRES_URL``).  No remote or
    implicit fallback is attempted.
    """

    if not admin_url:
        raise StrictExecutionError(
            "postgresql_authority_missing", kernel_key="strict.provisioning"
        )
    try:
        import psycopg
        from psycopg import sql
        from psycopg.conninfo import conninfo_to_dict, make_conninfo

        source = conninfo_to_dict(admin_url)
        database = _database_name(run_ref)
        maintenance = dict(source)
        maintenance["dbname"] = maintenance.get("dbname") or "postgres"
        with psycopg.connect(
            make_conninfo(**maintenance), autocommit=True
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT 1 FROM pg_database WHERE datname = %s", (database,)
                )
                if cursor.fetchone() is None:
                    cursor.execute(
                        sql.SQL("CREATE DATABASE {} ").format(sql.Identifier(database))
                    )
        target = dict(source)
        target["dbname"] = database
        database_url = make_conninfo(**target)
        migration_path = Path(migration_root)
        with psycopg.connect(database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "CREATE TABLE IF NOT EXISTS public.sensiblaw_schema_migration (migration_name text PRIMARY KEY, content_sha256 text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now())"
                )
                for path in sorted(migration_path.glob("*.sql")):
                    digest = hashlib.sha256(path.read_bytes()).hexdigest()
                    cursor.execute(
                        "SELECT content_sha256 FROM public.sensiblaw_schema_migration WHERE migration_name = %s",
                        (path.name,),
                    )
                    prior = cursor.fetchone()
                    if prior is not None:
                        if str(prior[0]) != digest:
                            raise StrictExecutionError(
                                "postgresql_authority_missing",
                                diagnostic_path=f"migration hash mismatch: {path.name}",
                                kernel_key="strict.migrations",
                            )
                        continue
                    cursor.execute(path.read_text(encoding="utf-8"))
                    cursor.execute(
                        "INSERT INTO public.sensiblaw_schema_migration (migration_name, content_sha256) VALUES (%s, %s)",
                        (path.name, digest),
                    )
        return database_url, database
    except StrictExecutionError:
        raise
    except Exception as error:
        raise StrictExecutionError(
            "postgresql_authority_missing",
            diagnostic_path=str(error),
            kernel_key="strict.provisioning",
        ) from error


__all__ = ["provision_local_postgres"]
