# COMPACTIFIED_CONTEXT

## Purpose
Compact snapshot of intent while applying the get-shit-done and update-docs-todo-implement workflows for Sprint S6 execution.

## Objective
Close S6 (done) and plan S7 surfaces (interfaces, activation metadata, cross-doc topology) with docs/TODO sequencing before code.

## Near-term intent (S7)
- Sprint S7 tracks: C) Human interfaces (snapshotted/locked), A) fact-driven activation (exposed via CLI/API, still non-reasoning), B) cross-document topology.
- Sequencing: C → A → B. Feature flags stay in place for new payloads; deterministic ordering + schema versioning required.

## Completed prior milestones
- Sprint S5: actors, actions/objects, scopes, lifecycle, graph projection, stability hardening — shipped and flag-gated.
- Sprint S6: query API, explanation surfaces, projections, alignment, schema stubs, and guard review completed; no-reasoning contract enforced.

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
