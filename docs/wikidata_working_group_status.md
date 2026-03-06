# Wikidata Working Group Status

Last updated: 2026-03-07

This is the single working-group link for the bounded Wikidata control-plane
work in SensibLaw/ITIR. Keep this document current and treat it as the top-level
entry point for Niklas, Ege, Peter, and related reviewers.

## Current focus
- bounded slice remains `P31` / `P279`
- goal is deterministic diagnostics and review support, not ontology fixes
- qualifier drift is explicitly deferred until the `P31` / `P279` pack is broader

## Current artifacts
- Diagnostic taxonomy:
  - `docs/ontology_diagnostic_taxonomy_wikidata_v0_1.md`
- Projection spec:
  - `docs/wikidata_epistemic_projection_operator_spec_v0_1.md`
- Report contract:
  - `docs/wikidata_report_contract_v0_1.md`
- Review template:
  - `docs/planning/wikidata_working_group_review_template_20260307.md`
- Latest seeded review pass:
  - `docs/planning/wikidata_working_group_review_pass_20260307.md`

## Current demo / review pack
- Primary local slice:
  - `tests/fixtures/wikidata/live_p31_p279_slice_20260307.json`
- Current CLI paths:
  - `sensiblaw wikidata build-slice`
  - `sensiblaw wikidata project`

## Confirmed current examples
### Mixed-order live case
- `Q9779` (`alphabet`)
- `Q8192` (`writing system`)
- status: currently live on reviewed item pages and suitable as the primary
  mixed-order example

### SCC live case
- `Q22652` (`urban green space`)
- `Q22698` (`park`)
- status: confirmed on 2026-03-07 from a live Wikidata SPARQL query showing
  reciprocal `P279` edges

### Historical / thread-derived example
- `referendum` / `plebiscite`
- status: keep as historical discussion-thread material only unless revalidated
  from current live item/dump data

## Current report shape
The report now exposes:
- per-window structural diagnostics:
  - `mixed_order_nodes`
  - `p279_sccs`
  - `metaclass_candidates`
- unstable slots with severity:
  - `high`: non-zero -> non-zero state flip
  - `medium`: zero <-> non-zero state change
  - `low`: evidence/conflict delta only
- `review_summary` for working-group triage

## Current decisions
- Stay on `P31` / `P279` before qualifier drift.
- Use local entity-export importer to grow review slices instead of hand-editing
  all JSON.
- Treat canonical text/token/lexeme layers as strictly separate from Wikidata
  semantics.

## Immediate next actions
1. Import more real `P31` / `P279` neighborhoods with `wikidata build-slice`.
2. Add at least one more current live SCC neighborhood and one more current live
   mixed-order neighborhood.
3. Re-run the seeded review pass after the broader slice is assembled.
4. Only then open phase-2 qualifier drift work.
