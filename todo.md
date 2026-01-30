# TODO

- Milestone (current): **Sprint S6 — Normative Reasoning Surfaces (Non-Judgmental)** — in progress.
- Previous milestone: **Sprint S5 — Normative Structure & Reach** — ✅ complete.
- Active sprint focus: deliver S6 read-only surfaces over obligations without adding reasoning/ontology/ML.

- S6 sequencing (execute in order):
  1) S6.1 Obligation Query API (read-only filters by actor/action/object/scope/lifecycle; respect flags) — ✅ done
  2) S6.2 Explanation & trace surfaces (atoms → spans, deterministic ordering) — ✅ done
  3) S6.3 Cross-version obligation alignment (unchanged/modified/added/removed with metadata deltas) — ✅ done
  4) S6.4 Normative view projections (actor/action/timeline/clause views; deterministic) — ✅ done
  5) S6.5 External consumer contracts (versioned JSON schemas for obligation/explanation/diff/graph) — 🚧 stubs seeded (query, explanation, alignment)
  6) S6.6 Hard stop & gate review (no-reasoning guard doc and red-flag tests) — ✅ done

- S6 guardrails: clause-local, text-derived only; identity/diff invariants frozen; outputs are read-only and deterministic; no invented nodes/edges; no compliance judgments.
- Tests-first rule: add pytest coverage for each sub-sprint before wiring code; feature-flag new surfaces if identity/output risk exists.

- Near-term task focus
  - Freeze schema versions after any final tweaks; bump versions explicitly if changed.
  - Decide next sprint direction (A compliance simulation, B cross-doc norm topology, C human interfaces).
  - Sprint 9 UI hardening (read-only, non-semantic):
    - Add fixture-mode rendering for Text & Concepts, Knowledge Graph, Case Comparison tabs (query param + env overrides).
    - Provide test fixtures under `tests/fixtures/ui` and unit checks for shape/forbidden language.
    - Add Playwright smoke (opt-in) asserting fixtures render and no mutation controls/forbidden terms.
    - Utilities tab: show “Labs / not covered by Sprint 9 invariants” banner; keep read-only.
  - Sources (ingestion) discipline:
    - Add AustLII SINO search adapter (deterministic URL builder + parser; rate-limited).
    - Add AustLII fetch adapter (HTML/PDF, provenance only, rate-limited).
    - Add citation normalisation helpers + tests (JADE/AustLII/PDF alignment).
    - Add storage guard tests (DB delta, compression ratio) using one PDF fixture.
  - Citation-follow expansion (bounded, non-semantic):
    - Implement citation extraction → resolution → fetch → ingest with depth/volume bounds.
    - Default resolver order: already-ingested → local → JADE (MNC) → AustLII (URL/search) → unresolved.
    - Add orchestration tests and ensure provenance is recorded outside identity hashes.

- Backlog (deferred)
  - Ingestion-to-query foundation — PDF → parsed artifacts → SQLite/FTS → traversal API → Graphviz DOT render with NLP Sprints 1–2 hooks (reactivate explicitly if needed).

- Dependencies/infra to track
  - None new for S6; continue using spaCy/Graphviz/SQLite baseline.
