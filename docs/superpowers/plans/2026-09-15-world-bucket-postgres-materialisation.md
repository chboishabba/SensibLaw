# World Bucket Postgres Materialisation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist a bounded `WikimediaWorldWalk` as an append-only, queryable Postgres world bucket with explicit publication projection and materialisation receipts, without JSON/JSONB or regex world parsing.

**Architecture:** Keep `WikimediaWorldWalk` as the local inquiry producer and Postgres as the current durable materialisation layer. A normalized schema stores bucket identity, nodes, typed growth receipts, selected publication projection, and append-only materialisation transitions. Persistence does not publish to IPFS/eRDFa, promote truth, or turn browsing history into a public projection.

**Tech Stack:** Python 3 dataclasses and DB-API/psycopg-compatible connections; PostgreSQL normalized tables; existing SensibLaw `StatementBundle`; DASHI Agda parity owner.

**Spec:** `docs/planning/wikimedia_world_bucket_walk_20260915.md`

## Global Constraints

- No JSON, NDJSON, JSONL, JSONB, or regex semantic/world parsing in the new production path.
- World growth and persistence remain candidate-only and do not create semantic authority or truth promotion.
- Persistence is append-only: replay is idempotent; conflicting mutation must not rewrite prior evidence.
- `local bucket != published graph`; publication selection must not encode Reading Trail / browsing history.
- Materialisation state is orthogonal to authority: local bytes, a mirror, or a locator cannot pay an evidentiary obligation by themselves.
- eRDFa/IPFS remain later export/publication surfaces; this tranche records only logical projection identity and locators.

---

### Task 1: Typed bucket projection and JSON/regex removal

**Files:**
- Modify: `src/ontology/wikimedia_world_walk.py`
- Modify: `tests/test_wikimedia_world_walk.py`

**Interfaces:**
- Consumes: `WorldWalkResult`, explicit selected node IDs.
- Produces: typed `WorldBucketProjection` with deterministic binary-field digest and structural QID validation.

- [ ] Write failing tests requiring a typed projection and absence of `json`/`re` imports.
- [ ] Replace regex QID validation with structural ASCII-digit validation.
- [ ] Replace canonical JSON digesting with deterministic length-prefixed field hashing.
- [ ] Preserve candidate-only/no-promotion/no-live-publication firewalls.
- [ ] Run focused tests and commit.

### Task 2: Normalized append-only Postgres schema

**Files:**
- Create: `database/postgres_migrations/182_world_bucket_append_only_materialisation.sql`
- Create: `tests/test_world_bucket_postgres_schema.py`

**Interfaces:**
- Produces tables `sl_world_bucket`, `sl_world_bucket_node`, `sl_world_growth_receipt`, `sl_world_bucket_projection`, `sl_world_bucket_projection_member`, `sl_world_materialisation_receipt`.

- [ ] Write schema tests requiring normalized columns and forbidding JSON/JSONB.
- [ ] Add primary/foreign keys and candidate-only checks.
- [ ] Add mutation-rejection triggers for UPDATE/DELETE.
- [ ] Keep all historical materialisation transitions append-only.
- [ ] Run focused tests and commit.

### Task 3: Postgres persistence adapter

**Files:**
- Create: `src/storage/postgres/world_bucket_store.py`
- Create: `tests/test_world_bucket_postgres_store.py`

**Interfaces:**
- Consumes: `WorldWalkResult`, `WorldBucketProjection`, materialisation receipts.
- Produces: idempotent `INSERT ... ON CONFLICT DO NOTHING` writes only.

- [ ] Write fake-connection tests first for bucket/receipt/projection persistence and replay.
- [ ] Implement deterministic IDs and normalized inserts with no UPDATE/DELETE.
- [ ] Add materialisation transition append function (`skeleton`, `reference_only`, `full_local`, `cold_local`, `federated_only`).
- [ ] Run focused tests and commit.

### Task 4: Agda parity owner

**Files:**
- Create: `DASHI/Interop/SensibLawWorldBucketPostgresMaterialisationExact.agda` in `chboishabba/dashi_agda`.
- Modify: `DASHI/Interop/Everything.agda`.

**Interfaces:**
- Mirrors normalized table families, append-only transition state, and publication/materialisation firewalls.

- [ ] Define exact materialisation-state constructors and table-family coordinates.
- [ ] Prove/encode `local possession != authority`, `skeleton != exact-source adequacy`, `projection != browsing history`, and `replay != rewrite` firewalls.
- [ ] Export through `Everything.agda`.
- [ ] Type-check focused owner locally before claiming certification.

### Task 5: Mabo specimen persistence seam

**Files:**
- Create or modify a focused Mabo/world-walk runner only after Tasks 1–4 are verified.

**Interfaces:**
- Consumes: bounded Mabo world walk.
- Produces: durable PG bucket plus selected proof/read projection; no IPFS publication.

- [ ] Persist one bounded Mabo bucket.
- [ ] Reopen skeleton/projection without requiring full source bytes.
- [ ] Demonstrate exact-source consumer remains unpaid until full source is reacquired.
- [ ] Record receipts and stop before UI work or live IPFS publication.
