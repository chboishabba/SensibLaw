# Postgres Migrations

- Location for the Postgres schema migrations; run in lexical order.
- Apply with `scripts/apply_pg_migrations.sh` (honours `PG*` env vars or `DATABASE_URL`).
- Designed for fresh databases—no attempt to carry forward SQLite state.
- Supersedes the ad-hoc SQL under `migrations/` and `schemas/migrations/`, which are kept only for reference.
