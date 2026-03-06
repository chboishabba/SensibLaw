# Wikidata Working Group Status

Last updated: 2026-03-07

This is the single working-group link for the bounded Wikidata control-plane
work in SensibLaw/ITIR. Keep this document current and treat it as the top-level
entry point for Niklas, Ege, Peter, and related reviewers.

## Current focus
- bounded slice now includes structural `P31` / `P279` review plus phase-2
  qualifier drift on bounded qualifier-bearing properties
- goal is deterministic diagnostics and review support, not ontology fixes
- qualifier drift is now active in bounded form

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
- Current pack status:
  - 2 confirmed current mixed-order neighborhoods
  - 2 confirmed current live SCC neighborhoods
  - 1 qualifier-drift fixture for bounded phase-2 diagnostics

## Confirmed current examples
### Mixed-order live case
- `Q9779` (`alphabet`)
- `Q8192` (`writing system`)
- status: currently live on reviewed item pages and suitable as the primary
  mixed-order example

### Mixed-order live case
- `Q21169592` (`Na(+)-translocating NADH-quinone reductase subunit A CTL0002`)
- `Q7187` (`gene`)
- status: confirmed on 2026-03-07 from a live Wikidata SPARQL query showing the
  item is both `P31` and `P279` gene

### SCC live case
- `Q22652` (`urban green space`)
- `Q22698` (`park`)
- status: confirmed on 2026-03-07 from a live Wikidata SPARQL query showing
  reciprocal `P279` edges

### SCC live case
- `Q52040` (`High German`)
- `Q188` (`German`)
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
- qualifier drift:
  - `high`: qualifier property set change
  - `medium`: qualifier signature change without property-set change
  - `low`: entropy-only change
- `review_summary` for working-group triage

## Current decisions
- `P31` / `P279` efficacy is proven at medium gate.
- Qualifier drift is the active next phase.
- Use local entity-export importer to grow review slices instead of hand-editing
  all JSON.
- Treat canonical text/token/lexeme layers as strictly separate from Wikidata
  semantics.

## Immediate next actions
1. Import qualifier-bearing real slices with `wikidata build-slice`.
2. Re-run the seeded review pass with at least one real qualifier-drift case in
   addition to the structural pack.
3. Validate whether property-set vs signature-set severity is sufficient for
   reviewers.
4. Only after that consider expanding beyond bounded qualifier drift.
