# COMPACTIFIED_CONTEXT

## Purpose
Compact snapshot of intent while applying the get-shit-done and update-docs-todo-implement workflows for Sprint S6 execution.

## Objective
Close S5 (done) and execute S6 surfaces (query, explanation, schemas) with docs/TODO sequencing before code.

## Near-term intent
- Sprint S5 completed: actors, actions/objects, scopes, lifecycle, graph projection, and stability hardening are shipped and flag-gated.
- Sprint S6 underway: S6.1 query API ✅, S6.2 explanation surfaces ✅, S6.4 projections ✅; S6.5 schema stubs seeded (query/explanation/alignment). Remaining: S6.3 alignment implementation, S6.5 finalize schemas, S6.6 guard review.
- Tests-first discipline remains for each S6 sub-sprint; keep feature flags available if new surfaces could affect identity or outputs.

## Priority order (S6 sequencing)
1) S6.1 Obligation Query API (read-only filters, flag-respecting) ✅  
2) S6.2 Explanation & trace surfaces ✅  
3) S6.3 Cross-version obligation alignment — ✅  
4) S6.4 Normative view projections — ✅  
5) S6.5 External consumer contracts (versioned schemas; stubs seeded) — schemas v1 seeded (query/explanation/alignment)  
6) S6.6 Hard stop & gate review (no-reasoning guard tests) — ✅

## Milestone scope
- Deliver read-only, deterministic surfaces over the existing normative lattice: queries, explanations, alignment, projections, schemas.
- Keep LT-REF, CR-ID/DIFF, OBL-ID/DIFF, and provenance invariants frozen; no compliance or interpretive behavior.

## Dependencies / infra constraints
- None new; spaCy/Graphviz/SQLite remain the baseline.

## Assumptions
- Python 3.11 target with 3.10 fallback; Ruff formatting.
- Clause-local, text-derived extraction; no cross-clause inference.

## Open questions
- Do we need richer fixtures for multi-verb phrases or nested scopes as we exercise S6 queries/views?
- Which consumers (CLI, API, Streamlit) should receive the first query/explanation surface?
- How should alignment reports surface metadata deltas without touching identity? (to be defined in S6.3)
