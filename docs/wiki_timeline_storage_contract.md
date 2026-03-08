# Wiki Timeline Storage Contract (AAO Exports vs DB Persistence)

This contract clarifies where wiki timeline artifacts live and what is
considered canonical storage vs export formats.

## Goal
- Keep wiki timeline extraction deterministic and reproducible.
- Allow DB-first workflows (query/joins/dedupe) without breaking existing UI
  consumers that read exported JSON payloads.

## Core Rule
**JSON is an export artifact. The canonical persisted store is a database.**

In the current design, wiki timeline extraction may still emit JSON for
visualization and fixtures, but canonical persistence lives in the shared root
SQLite store and should be typed/queryable first.

## Storage Layers

### Export artifacts (JSON)
- Purpose: UI visualization and fixture-friendly snapshotting.
- Location (current):
  - `SensibLaw/.cache_local/wiki_timeline_*_aoo.json`
- Contract:
  - Deterministic `sort_keys=true` emission.
  - Non-authoritative; safe to delete and regenerate.
  - Not required to be the storage shape used internally by the canonical DB.
  - Revision-comparison reports derived from wiki snapshots / AAO payloads are
    also export artifacts. They are review surfaces, not canonical storage.

### Persistent store (SQLite)
- Purpose: queryable storage of extracted AAO runs/events and audit metadata.
- Location (recommended, gitignored):
  - `.cache_local/itir.sqlite`
- Contract:
  - Idempotent writes per `(run_id, event_id)` primary keys.
  - DB rows are rebuildable from the same timeline input + profile + compiler
    version pins.
  - Canonical storage should use typed tables for route/query/report-critical
    data rather than JSON blobs stored "for the hell of it".
  - Full lossless reconstruction of every historical JSON export shape is not a
    requirement. The requirement is preserving canonical product semantics:
    route payloads, parity-critical fields, joins, ordering, and audit metadata.
- Implementation (current):
  - `scripts/wiki_timeline_aoo_extract.py` persists to SQLite by default (`--db-path`),
    and can be disabled via `--no-db`.

## Run Identity (Deterministic)
Each persistence run must have a deterministic `run_id` derived from stable
inputs, e.g.:
- timeline content hash
- extraction profile hash (or `profile_id@profile_version` + sha256)
- parser version metadata (model + version)
 - extractor code hash (to prevent silent mixing of different compiler logic)

The goal is: **same inputs produce the same `run_id`**, enabling dedupe and
repeatable builds.

## Canonical DB Shape
The DB persistence layer stores:
- a run record (`run_id`, hashes, profile metadata, generated_at)
- event payloads keyed by `(run_id, event_id)` with extracted anchor fields
  (year/month/day) for indexing
- typed supporting tables for actors, links, objects, steps, structural atoms,
  bridge data, and other route/query/report-critical fields
- compatibility columns may temporarily remain during migration, but they are
  not the target architecture

The canonical DB is not required to preserve arbitrary unused export tails if
those tails are not part of stable product behavior. If a field is needed for:
- route rendering
- parity checks
- filtering/sorting/joining
- reporting or auditability
it belongs in typed storage.

Schema evolution must be additive (new columns/tables) with deterministic
migrations; do not rewrite old runs in place.

## UI Contract
The Svelte graphs should be DB-first:
- Preferred: hydrate graph payloads from the canonical SQLite store
  (`.cache_local/itir.sqlite`).
- Legacy fallback: read `wiki_timeline_*_aoo.json` export artifacts from disk
  (regression/debug only).

Implementation notes:
- itir-svelte loads AAO payloads via the Python query helper:
  `SensibLaw/scripts/query_wiki_timeline_aoo_db.py`
- Repo-local backfill helper (one-time migration from legacy JSON into DB):
  `SensibLaw/scripts/import_wiki_timeline_aoo_json_to_db.py`
- Bounded local chat samples for tokenizer/storage experiments must not be
  written into canonical wiki timeline tables. Use an isolated test DB such as
  `.cache_local/itir_chat_test.sqlite` until retention/redaction policy exists.
