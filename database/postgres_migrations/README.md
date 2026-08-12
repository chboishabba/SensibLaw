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
- `086_consumer_indexed_reopenable_runtime.sql` adds the durable F/P/Q/R/O
  execution carrier, signed cumulative evidence, explicit open-world relevance,
  exact parser->argument support transport, identity/factor audits, and runtime
  measurement surfaces without replacing the set-based demand planner.
- `087_reopenable_runtime_hardening.sql` makes runtime history append-only by
  corrective event and permits durable Q->P reopening independently of the
  latest ephemeral planner row.  It preserves the original v1 view column order
  before appending diagnostics so upgrades are safe under PostgreSQL
  `CREATE OR REPLACE VIEW` rules.
- `088_progressive_reopenable_resolution.sql` adds cumulative H3/H6/H9
  preference/escalation surfaces.  Preference is explicitly non-proof and never
  writes `semantic_pnf_frontier_resolution` or identity witnesses.
- See `docs/reopenable_runtime_architecture.md` and
  `scripts/audit_reopenable_runtime_migrations.py` for the architecture and
  source-dependency audit.

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
