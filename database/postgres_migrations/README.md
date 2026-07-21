# Postgres Migrations

- Location for the Postgres schema migrations; run in lexical order.
- Apply with `scripts/apply_pg_migrations.sh` (honours `PG*` env vars or `DATABASE_URL`).
- Designed for fresh databases—no attempt to carry forward SQLite state.
- Supersedes the ad-hoc SQL under `migrations/` and `schemas/migrations/`, which are kept only for reference.
- `007_compiler_substrate.sql` is the additive generic compiler runtime. It
  stores immutable declarations, documents, builds/dependencies, shared
  annotations, factorised PNF structure, typed meets, factor revisions, and
  unresolved demands without requiring a legal-ontology row.
