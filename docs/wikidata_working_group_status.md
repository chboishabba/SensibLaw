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
- Current live finder mode:
  - per-property raw-row WDQS candidate scan (`per_property_raw_rows_v1`)
  - no label service or grouped qualifier aggregation in the candidate phase
- Current pack status:
  - 2 confirmed current mixed-order neighborhoods
  - 2 confirmed current live SCC neighborhoods
  - 1 real imported qualifier-bearing baseline slice
  - 1 bounded synthetic qualifier-drift fixture
  - live finder now produces confirmed revision-pair qualifier-drift cases

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
  - status: synthetic review fixture remains useful as a deterministic
    regression/demo case, but is no longer the only drift example
- Repo-pinned live drift case:
  - `tests/fixtures/wikidata/q100104196_p166_2277985537_2277985693/slice.json`
  - paired projection:
    - `tests/fixtures/wikidata/q100104196_p166_2277985537_2277985693/projection.json`
  - status: primary repo-stable live qualifier-drift example
- Second repo-pinned live drift case:
  - `tests/fixtures/wikidata/q100152461_p54_2456615151_2456615274/slice.json`
  - paired projection:
    - `tests/fixtures/wikidata/q100152461_p54_2456615151_2456615274/projection.json`
  - status: second repo-stable live qualifier-drift example covering `P54`
- Live finder results (2026-03-07):
  - narrow `P166` scan:
    - `candidate_count=12`
    - `stable_baseline_count=10`
    - `confirmed_drift_case_count=0`
    - `failure_count=0`
  - broad `P166/P39/P54/P6` scan:
    - `candidate_query_mode=per_property_raw_rows_v1`
    - `candidate_count=47`
    - `confirmed_drift_case_count=2`
    - `stable_baseline_count=23`
    - `failure_count=0`
    - first confirmed live materialized case:
      - `Q100104196|P166`
      - revisions `2277985537 -> 2277985693`
      - severity `medium`
      - drift shape: qualifier signature change with the qualifier property set
        unchanged (`P585` only)
      - now promoted into repo fixtures under
        `tests/fixtures/wikidata/q100104196_p166_2277985537_2277985693/`
    - currently reported confirmed cases in
      `/tmp/wikidata_qualifier_scan/scan_report.json`:
      - `Q100104196|P166` revisions `2277985537 -> 2277985693` (`medium`)
      - `Q100152461|P54` revisions `2456615151 -> 2456615274` (`medium`)
    - earlier broad run also surfaced:
      - `Q100243106|P54` revisions `2462692998 -> 2462767606` (`medium`)
      - useful as a secondary observed live case, but not the current primary
        materialized example

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
- A true live revision-pair qualifier-change case has now been captured
  reproducibly by the live finder.
- Keep the bounded synthetic drift fixture as regression/demo coverage, not as
  the primary evidence that live drift exists.
- Treat canonical text/token/lexeme layers as strictly separate from Wikidata
  semantics.

## Immediate next actions
1. Re-run the seeded review pass with the importer-backed qualifier baseline and
   the repo-pinned `Q100104196|P166` and `Q100152461|P54` live drift cases.
2. Validate whether `medium` severity for signature-only drift remains the right
   reviewer-facing choice on the confirmed live cases.
3. Decide whether the earlier observed `Q100243106|P54` case is still worth
   pinning, or whether the current two-case live pack is sufficient.
4. Only after that consider expanding beyond bounded qualifier drift.
