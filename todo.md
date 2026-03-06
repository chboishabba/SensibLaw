# SensibLaw TODO

## Wikidata
- [x] Implement the bounded `P31` / `P279` Wikidata control-plane prototype described in `docs/planning/wikidata_transition_plan_20260306.md`.
- [x] Add a bounded live-case fixture anchored on the current `alphabet` / `writing system` example.
- [x] Define a reproducible two-window Wikidata slice for EII and SCC diagnostics.
- [x] Add deterministic JSON report schema and CLI surface for Wikidata diagnostics.
- [x] Run the first Niklas/Ege/Peter review pass using `docs/planning/wikidata_working_group_review_template_20260307.md`.
- [x] Define the v0.1 reviewer-facing report contract and severity/ranking rules.
- [x] Add a local entity-export importer (`wikidata build-slice`) so review slices do not require hand-curated JSON.
- [x] Maintain a single working-group status doc at `docs/wikidata_working_group_status.md`.
- [ ] Extend phase-1 diagnostics to qualifier drift after the `P31` / `P279` core report is stable.

## Medium-Term Targets
- [ ] Add jurisdiction-aware GWB action review as a test target: be able to assess George W. Bush timeline actions under pinned U.S. law and Australian law, with U.S. law first.
- [ ] Build a U.S.-law seed set for GWB covering relevant actions, proceedings, and court/hearing material so specific events can be pinned to authoritative legal sources before broader cross-jurisdiction comparison.
