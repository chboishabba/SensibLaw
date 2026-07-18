# Postgres Migrations

- Migrations run in lexical order.
- Apply with `scripts/apply_pg_migrations.sh`; standard `PG*` variables or
  `DATABASE_URL` select the database.
- The track is designed for fresh PostgreSQL databases. It does not silently
  carry forward SQLite or filesystem-JSON runtime state.
- Ad-hoc SQL under `migrations/` and `schemas/migrations/` is retained only as
  historical reference.

## Runtime ownership

PostgreSQL is the operational store for the active corpus/compiler path.
Migration `006_generic_compiler_runtime.sql` adds capability-oriented schemas:

- `corpus`: immutable source/canonical content, documents, occurrences, spans;
- `language`: lexeme dictionary, compact token/posting streams, annotations;
- `algebra`: declarations, alternatives, factors, constraints, relations,
  residuals, and pressure assessments;
- `pnf`: generic factor graphs;
- `evidence`: local evidence, external snapshots, generic assertions;
- `resolution`: demands, typed meets, assessments, and refinements;
- `execution`: builds, dependencies, schedules, and failure receipts;
- `governance`: review/readiness decisions without editing authority.

The compiler schema does not introduce legal-, Wikidata-, WorldMonitor-, GWB-,
or AU-specific table families. Domain and registry knowledge enters as
versioned declarations, evidence snapshots, and assertions. Existing legal
ontology tables remain downstream domain projections and are not prerequisites
for corpus compilation.

Structured semantic state is relational. Exact source bytes and dense encoded
streams use `bytea`. JSON is reserved for explicit import/export, fixtures, and
portable boundary receipts; the default compiler does not emit semantic JSON
files.

Logical `language.lexeme.lexeme_id` values are 4-byte `integer` identities.
Physical token compression uses corpus-local frequency-ranked symbols and
unsigned-varint/delta-coded `bytea` chunks. A relational row per token is only
an optional sparse projection, not the canonical dense representation.
