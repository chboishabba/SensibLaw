# UI Tab Contracts (Sprint 9 Discipline)

This document defines the **non-semantic, deterministic contracts** for the Streamlit tabs. Every visible tab must either satisfy these contracts or fail tests loudly. The goal is to keep the UI a **read-only projection** of frozen payloads.

## Fixture mode (for tests and demos)
- Enable by adding query params to the Streamlit URL, or via environment variables.
- Default fixture directory: `tests/fixtures/ui`.
- If a fixture is requested and found, the tab renders **only** fixture data (no network/DB calls, no mutation).
- All fixture renders are read-only and must avoid forbidden terms: `compliance, breach, prevails, valid, invalid, stronger, weaker, satisfies, violates, binding, override`.

## Tabs

### Documents
- Existing ingestion UI; unchanged in Sprint 9 scope.

### Collections
- Contract already enforced via unit/CLI + Playwright: structural diff only, deterministic manifest/export, no mutation.

### Text & Concepts (fixture contract)
- Input: `concepts_fixture` query param or `SENSIBLAW_CONCEPTS_FIXTURE`.
- Renders: input text, concept matches list, concept cloud counts.
- No pipeline execution in fixture mode; no semantic language.

### Knowledge Graph (fixture contract)
- Input: `graph_fixture` query param or `SENSIBLAW_GRAPH_FIXTURE`.
- Renders: node count, edge count, edge list; every edge must carry a citation field.
- No inferred edges or reasoning; read-only JSON.

### Case Comparison (fixture contract)
- Input: `case_fixture` query param or `SENSIBLAW_CASE_FIXTURE`.
- Renders: added/removed/unchanged obligation IDs exactly as provided; shows IDs verbatim.
- No scoring, no “stronger/weaker/prevails”.

### Utilities
- Remains a labs surface; must display a banner that it is **not** covered by Sprint 9 invariants and performs no mutations.

## Testing expectations
- Unit: fixture shape checks (counts, citations present, forbidden terms absent).
- Playwright (opt-in via `RUN_PLAYWRIGHT=1`): load page with fixture query params; assert each tab renders fixture data, has no mutation controls, and contains no forbidden language.

