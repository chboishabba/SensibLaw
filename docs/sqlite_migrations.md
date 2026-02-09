# SQLite Migrations (Ontology DB)

SensibLaw has multiple SQLite schemas in the repo:

- **VersionedStore** (PDF ingest) in `src/storage/versioned_store.py`
- **Core storage** (story/event ingest) in `src/storage/schema.sql`
- **Ontology DB** (legal systems/sources, actors, concept substrate) managed by
  the SQLite migrations in `database/migrations/`

This doc references all three so you don't confuse them, but it covers only the
**Ontology DB** migration track (the `database/migrations/` directory + runner).

## Where migrations live

- Migrations directory: `database/migrations/`
- Runner: `src/sensiblaw/db/migrations.py` (`MigrationRunner`)
- Entry point: `src/sensiblaw/db/dao.py` (`ensure_database(connection)`)

## Idempotency contract

`ensure_database()` is called by multiple CLI commands. It must be safe to call
repeatedly against an existing Ontology DB.

To enforce that:

- Applied migrations are tracked in a `schema_migrations` table (filename + checksum).
- Each migration file is executed at most once per DB.
- If a migration file’s contents change after it’s been applied (checksum mismatch),
  the runner errors: you must create a new migration file instead.

This is required because some migrations are intentionally non-repeatable
(e.g., transitional table swaps like `legal_systems` normalization).

## DB selection guardrail

Do not point the ontology migration runner at the VersionedStore ingest DB
(`data/corpus/ingest.sqlite`). They are different schemas.

If you want an ontology DB locally, create one under a gitignored path, e.g.:

- `SensibLaw/.cache_local/sensiblaw_ontology.sqlite`

Then run any ontology CLI command with `--db` pointing at that file; the runner
will create the required tables on first run.
