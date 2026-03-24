# Wikidata Working Group Status

Last updated: 2026-03-25

This is the single working-group link for the bounded Wikidata control-plane
work in SensibLaw/ITIR. Keep this document current and treat it as the top-level
entry point for Niklas, Ege, Peter, and related reviewers.

If you need one short plain-language handoff that also works for the Zelph
developer, start with:
- `../../docs/planning/wikidata_zelph_single_handoff_20260325.md`

Treat this status note as the Wikidata-specific detailed appendix after that
shared handoff.

## Current focus
- bounded slice now includes structural `P31` / `P279` review plus phase-2
  qualifier drift on bounded qualifier-bearing properties
- parthood pilot pack (`P361`/`P527`) now has a pinned fixture + expected
  projection under `tests/fixtures/wikidata/parthood_pilot_pack_20260308`
- importer-backed parthood/mereology pack now also exists under
  `tests/fixtures/wikidata/parthood_imported_pack_20260308`
- goal is deterministic diagnostics and review support, not ontology fixes
- qualifier drift is now active in bounded form
- current phase-2 posture is split deliberately:
  - real imported qualifier-bearing baseline slices via entity export
  - bounded synthetic drift fixture for explicit property-set change review
- current framing is now explicitly domain-agnostic:
  - finance/property examples are useful, but not special
  - software/project/artifact examples like `GNU` / `GNU Project` are equally
    valid demonstrations of entity-kind collapse
  - the next benchmark-facing lane should mine structural hotspots, not assume
    a clean ontology by flattening `P31`/`P279` away

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
- Extraction/enrichment boundary note:
  - `docs/planning/extraction_enrichment_boundary_20260307.md`
- Bounded mereology/parthood note:
  - `docs/planning/wikidata_mereology_parthood_note_20260307.md`
- Property/constraint pressure-test note:
  - `docs/planning/wikidata_property_constraint_pressure_test_20260307.md`
- Mereology pilot pack:
  - `tests/fixtures/wikidata/parthood_pilot_pack_20260308`
- Import-backed mereology pack:
  - `tests/fixtures/wikidata/parthood_imported_pack_20260308`
- Current packed artifact:
  - `tests/fixtures/wikidata/parthood_pilot_pack_20260308/projection.json`
- import-backed parthood/artifact:
  - `tests/fixtures/wikidata/parthood_imported_pack_20260308/projection.json`

## Current demo / review pack
- Primary local slice:
  - `tests/fixtures/wikidata/live_p31_p279_slice_20260307.json`
- Current CLI paths:
  - `sensiblaw wikidata build-slice`
  - `sensiblaw wikidata project`
  - `sensiblaw wikidata find-qualifier-drift`
- Current test-suite interface (flag this as the primary local debug surface for
  the sprint):
  - `tests/test_wikidata_cli.py`
    - CLI contract coverage for `build-slice`, `project`, and
      `find-qualifier-drift`-adjacent fixture flows
  - `tests/test_wikidata_projection.py`
    - projection/report semantics, SCC/mixed-order/parthood diagnostics, and
      bounded qualifier-drift expectations
  - `tests/test_wikidata_finder.py`
    - live/repo-pinned qualifier-drift candidate finder contract
  - `tests/test_ontology_cli_commands.py`
    - bridge import/report and external-ref batch/upsert round trips
  - `tests/test_lexeme_layer.py`
    - deterministic bridge resolution + emitted external-ref batch coverage
  - current sprint note:
    - use these tests as the first debug/function check before expanding the
      working-group pack or touching downstream UI surfaces
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
    - repo-pinned confirmed review cases:
      - `Q100104196|P166` revisions `2277985537 -> 2277985693` (`medium`)
      - `Q100152461|P54` revisions `2456615151 -> 2456615274` (`medium`)
    - earlier broad run also surfaced:
      - `Q100243106|P54` revisions `2462692998 -> 2462767606` (`medium`)
      - useful as a secondary observed live case, but not the current primary
        materialized example
    - latest successful fresh live validation run (2026-03-08, outside sandbox)
      surfaced:
      - `Q1000498|P166` revisions `2457306419 -> 2457306429` (`medium`)
      - treated as a fresh confirmed live candidate, not yet part of the pinned
        review pack

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
- 2026-03-08 live validation note (outside sandbox): the latest full scan run
  reproduced `Q1000498|P166` (`2457306419 -> 2457306429`) as the first
  confirmed medium candidate from a fresh candidate run.

## Current decisions
- `P31` / `P279` efficacy is proven at medium gate.
- Qualifier drift is the active next phase.
- Pinned live pack stays on `Q100104196|P166` + `Q100152461|P54` for now for
  reproducibility, while fresh live candidates are tracked separately.
- Current review assumption for active Wikidata diagnostics: use the newest pinned
  slice/revision as the baseline for bounded reporting by default, rather than
  running explicit historical backtracking on every pass; historical review is
  still available when it materially helps to disambiguate stability versus
  reversion.
- Historical rewind is now a trigger-based follow-up, not a default mode:
  - confirmed case from previous run disappears in a newer confirmed run,
  - severity for a focus pair changes materially between runs, or
  - property/set-specific review signals indicate potential data drift around the
    same slots.
- Property definitions and restrictions are in scope for the ontology lane when
  they interact with class use and constraints; they are not out-of-scope just
  because they are properties rather than classes.
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
- The next formalism-facing extension is not generic ontology cleanup; it is a
  bounded mereology/parthood lane. The current highest-yield question for the
  working group is typed/disambiguated parthood:
  - class-class parthood
  - instance-instance parthood
  - instance-class parthood
  - when inverse pairs are semantically valid vs merely redundant
- DASHI-style epistemic/projection machinery is a candidate downstream lens for
  this work, but it does not replace the bounded deterministic diagnostic layer.
- Financial-flow / time-series modeling is now explicitly recognized as a
  relevant adjacent use case for the group: timeseries, constraint interactions,
  subset-vs-total modeling, and graphing surfaces are useful diagnostic
  pressure tests even if they are not the first bounded executable slice.
- Label harmonization issues like `XXX subclass` vs `type of XXX` are useful as
  user-facing inconsistency signals, but should be treated as downstream
  diagnostic/reporting evidence, not as the primary ontology criterion.
- The current mereology/parthood lane should anchor on the actual property
  family (`P527`, `P361`, related parthood-like predicates), not just on
  abstract discussion.
- Competitor hotspot/consistency work built from Wikidata-derived ontologies is
  worth treating as pressure, but not as the design model to copy directly:
  the stronger repo posture is to preserve structural pathology provenance
  instead of collapsing it into a generic `subConceptOf` graph too early.

## Immediate next actions
1. Re-run the seeded review pass with the importer-backed qualifier baseline and
   the repo-pinned `Q100104196|P166` and `Q100152461|P54` live drift cases.
   DONE (2026-03-08): pinned seed fixtures and report contract expectations for
   `Q100104196|P166` and `Q100152461|P54` are still in place, with both
   fixture projections continuing to report `medium` qualifier signature drift.
   A fresh live scan attempt was rerun successfully with full network access
   (outside sandbox) and returned a confirmed live candidate (`Q1000498|P166`).
2. Validate whether `medium` severity for signature-only drift remains the right
   reviewer-facing choice on the confirmed live cases.
   DONE (2026-03-08): keep `medium` for signature-only drift; both confirmed
   pinned cases still align with this rule without state inversion.
3. Decide whether the earlier observed `Q100243106|P54` case is still worth
   pinning, or whether the current two-case live pack is sufficient.
   DONE (2026-03-08): do not pin `Q100243106|P54` for now; it is not in the
   latest confirmed set we can currently reproduce and is retained only as
   historical watch material.
4. Convert the new mereology/property notes into a bounded fixture-backed pilot
   pack (`P361`/`P527` typing, inverse validity, subset-vs-total examples).
   DONE (2026-03-08): importer-backed parthood pack now exists and is covered by
   projection regression tests.
5. Keep the mereology/property-pressure lane explicitly supportive of the
   frozen semantic v1.1 model rather than using it as a reason to widen the
   canonical schema before GWB + Australian cross-testing fails in a concrete
   way.
