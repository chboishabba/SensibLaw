# Postgres Migrations

- Location for the Postgres schema migrations; run in lexical order.
- Apply with `scripts/apply_pg_migrations.sh` (honours `PG*` env vars or `DATABASE_URL`).
- PostgreSQL is the sole active semantic persistence spine. SQLite is retained
  only for bounded legacy import/replay fixtures and must not become a runtime
  semantic authority.
- JSON is a detached presentation format. It may be emitted by projections but
  is never re-ingested as a graph, world-model, or follow-workflow input.
- Supersedes the ad-hoc SQL under `migrations/` and `schemas/migrations/`, which are kept only for reference.
- `007_compiler_substrate.sql` is the additive generic compiler runtime. It
  stores immutable declarations, documents, builds/dependencies, shared
  annotations, factorised PNF structure, typed meets, factor revisions, and
  unresolved demands without requiring a legal-ontology row.
- `024_generic_follow_projection.sql` persists derived-only, challengeable
  follow projections as rows with FK closure and exposes legal/non-legal views.

## Migration identifier guardrail

The directory currently contains duplicate `006_*` and `007_*` prefixes.
Filename plus content hash remains the applied-migration identity, so an
already-applied file must not be renamed in place. Until a
checksum-preserving renumbering plan is complete:

- every new migration must use a previously unused numeric prefix;
- reviewers must inspect full filenames rather than treating the prefix as a
  unique identifier;
- no migration may be copied into the deprecated SQLite or superseded
  reference tracks.
