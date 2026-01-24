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

- Backlog (deferred)
  - Ingestion-to-query foundation — PDF → parsed artifacts → SQLite/FTS → traversal API → Graphviz DOT render with NLP Sprints 1–2 hooks (reactivate explicitly if needed).

- Dependencies/infra to track
  - None new for S6; continue using spaCy/Graphviz/SQLite baseline.
