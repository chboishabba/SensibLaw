# Generic PostgreSQL compiler runtime

Date: 2026-07-18
Status: implementation tranche; database application still environment-bound

## Decision

PostgreSQL is the active operational store for new corpus, language, semantic
algebra, PNF, evidence, resolution, execution, and review work.

The compiler does not emit semantic JSON by default. JSON remains an explicit
boundary format for imports, exports, fixtures, debugging, and portable signed
receipts. The previous filesystem content-addressed JSON directory is retained
only behind `--emit-legacy-json` while callers migrate.

## Capability-oriented schema

The compiler migration is divided by reusable operations rather than domains:

```text
corpus      source/canonical content, documents, occurrences, spans
language    logical dictionary, compact streams, postings, annotations
algebra     declarations, alternatives, factors, constraints, relations,
            residuals, and pressure
a pnf       factor graphs
evidence    local evidence, external snapshots, generic assertions
resolution  demands, typed meets, assessments, refinements
execution   build keys, dependencies, schedules, failures
governance  readiness/review decisions without editing authority
```

Legal, Wikidata, WorldMonitor, GWB, and AU do not receive compiler-specific
schema families. They may contribute versioned declarations, evidence
snapshots, assertions, proof fixtures, and policy inputs through the generic
surfaces.

## Text and dictionary representation

The exact source and canonical text remain authoritative compressed/opaque
content. Dictionary and token structures are derived retrieval/compression
representations.

```text
stable logical lexeme_id: PostgreSQL integer
physical codec symbol: corpus/run-local frequency rank
encoded token stream: unsigned varint bytea
encoded offsets: monotone delta-varint bytea
posting blocks: compressed bytea
sparse token rows: optional query projection only
```

This avoids replacing short words with 8-byte `bigint` foreign keys. Stable
logical identity and frequency-optimized physical encoding remain separate.

## Direct runtime

`scripts/compile_corpus.py` now requires `--database-url` or `DATABASE_URL` for
the normal path. It inventories the corpus, compiles each distinct supported
document, and writes normalized PostgreSQL rows transactionally. Duplicate
paths for the same document add occurrence rows only. Per-document failures
produce failure receipts and do not abort the corpus.

The direct runtime persists:

- exact source and canonical content;
- document and path occurrences;
- dictionary entries and compact token/offset streams;
- annotation layers/nodes;
- algebra alternatives/factors/residuals;
- PNF graph membership;
- document-local evidence;
- unresolved demands;
- typed meets and factor refinements.

It performs no external network call, cross-document identity closure,
readiness promotion, or editing action.

## SQL projections

The migration supplies relational views rather than default JSON reports:

- `pnf.v_document_pnf`;
- `resolution.v_unresolved_demand`;
- `corpus.v_document_summary`;
- `governance.v_review_queue`;
- `execution.v_dependency_staleness`.

Additional export formats must be explicit commands over SQL queries; no export
format is authoritative.

## Migration integrity

`scripts/apply_pg_migrations.sh` now records immutable filename/content hashes
in `public.sensiblaw_schema_migration`. A changed migration with an already
recorded filename fails closed.

## Validation boundary

Unit tests validate varint/delta round trips, frequency ranking, generic schema
names, absence of domain-specific compiler tables, integer logical lexeme IDs,
compact `bytea` streams, and PostgreSQL-first CLI selection.

A live PostgreSQL test requires an available database and applied migrations.
The bounded acceptance proof is:

1. apply all PostgreSQL migrations;
2. compile `tests/fixtures/corpora/gwb-mini`;
3. query document summary, PNF, unresolved demands, meets, and refinements;
4. rerun and verify stable identities with no duplicate semantic rows;
5. run the same path against an AU fixture without a lane-specific compiler;
6. confirm no semantic JSON files are emitted.

## Legacy retirement

The new compiler path does not write to `ResolutionArtifactStore` or the
filesystem JSON object store. The older SQLite `VersionedStore` and unrelated
read models remain separate retirement decisions; they are not silently
rewritten by this tranche.
