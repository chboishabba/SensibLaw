# Wiki Timeline Storage Contract (AAO Exports vs DB Persistence)

This contract clarifies where wiki timeline artifacts live and what is
considered “canonical” storage vs “export” formats.

## Goal
- Keep wiki timeline extraction deterministic and reproducible.
- Allow DB-first workflows (query/joins/dedupe) without breaking existing UI
  consumers that read JSON payloads.

## Core Rule
**JSON is an export artifact. The canonical persisted store is a database.**

In v0.x, wiki timeline AAO extraction emits JSON for visualization, but may
persist the same content to a SQLite DB for stable query and downstream
materialization.

## Storage Layers

### Export artifacts (JSON)
- Purpose: UI visualization and fixture-friendly snapshotting.
- Location (current):
  - `SensibLaw/.cache_local/wiki_timeline_*_aoo.json`
- Contract:
  - Deterministic `sort_keys=true` emission.
  - Non-authoritative; safe to delete and regenerate.

### Persistent store (SQLite)
- Purpose: queryable storage of extracted AAO runs/events and audit metadata.
- Location (recommended, gitignored):
  - `SensibLaw/.cache_local/wiki_timeline_aoo.sqlite`
- Contract:
  - Idempotent writes per `(run_id, event_id)` primary keys.
  - DB rows are rebuildable from the same timeline input + profile + compiler
    version pins.
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

## Minimal DB Schema (v0.1)
The DB persistence layer stores:
- a run record (`run_id`, hashes, profile metadata, generated_at)
- event payloads keyed by `(run_id, event_id)` with extracted anchor fields
  (year/month/day) for indexing
- full event payload as JSON text for forward compatibility

Schema evolution must be additive (new columns/tables) with deterministic
migrations; do not rewrite old runs in place.

## UI Contract
The Svelte graphs should be DB-first:
- Preferred: hydrate graph payloads from the canonical SQLite store
  (`SensibLaw/.cache_local/wiki_timeline_aoo.sqlite`).
- Legacy fallback: read `wiki_timeline_*_aoo.json` export artifacts from disk
  (regression/debug only).

Implementation notes:
- itir-svelte loads AAO payloads via the Python query helper:
  `SensibLaw/scripts/query_wiki_timeline_aoo_db.py`
- Repo-local backfill helper (one-time migration from legacy JSON into DB):
  `SensibLaw/scripts/import_wiki_timeline_aoo_json_to_db.py`
