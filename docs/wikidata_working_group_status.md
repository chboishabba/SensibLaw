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
- current phase-2 posture is split deliberately:
  - real imported qualifier-bearing baseline slices via entity export
  - bounded synthetic drift fixture for explicit property-set change review

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
  - `sensiblaw wikidata find-qualifier-drift`
- Current pack status:
  - 2 confirmed current mixed-order neighborhoods
  - 2 confirmed current live SCC neighborhoods
  - 1 real imported qualifier-bearing baseline slice
  - 1 bounded synthetic qualifier-drift fixture

## Current phase-2 qualifier pack
- Real imported baseline slice:
  - `tests/fixtures/wikidata/real_qualifier_imported_slice_20260307.json`
  - built from:
    - `tests/fixtures/wikidata/entitydata_qualifier_q28792860_prev.json`
    - `tests/fixtures/wikidata/entitydata_qualifier_q28792860_current.json`
    - `tests/fixtures/wikidata/entitydata_qualifier_q1336181_prev.json`
    - `tests/fixtures/wikidata/entitydata_qualifier_q1336181_current.json`
  - status: importer-backed, real qualifier-bearing revision pairs, currently
    zero `qualifier_drift`
- Bounded drift demo:
  - `tests/fixtures/wikidata/qualifier_drift_slice_20260307.json`
  - status: synthetic review fixture retained because no confirmed live
    revision-pair qualifier-change case has been pinned locally yet

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
- Treat real imported zero-drift qualifier slices as valid baseline evidence,
  not failure.
- Keep the bounded synthetic drift fixture until a true live revision-pair
  qualifier-change case is captured reproducibly.
- Treat canonical text/token/lexeme layers as strictly separate from Wikidata
  semantics.

## Immediate next actions
1. Use `wikidata find-qualifier-drift` to rank qualifier-bearing candidates and
   scan recent revisions deterministically.
2. Promote the first confirmed live revision-pair qualifier-change case into
   the imported phase-2 pack.
3. Re-run the seeded review pass with the importer-backed qualifier baseline and
   any newly confirmed live drift case.
4. Only after that consider expanding beyond bounded qualifier drift.
