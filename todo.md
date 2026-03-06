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
- [x] Extend phase-1 diagnostics to qualifier drift after the `P31` / `P279` core report is stable.
- [x] Import real qualifier-bearing slices and add an importer-backed phase-2 baseline pack.
- [x] Add a deterministic live qualifier-drift finder that ranks candidates and scans revision pairs programmatically.
- [x] Find a true live revision-pair qualifier-change case with the live finder.
- [x] Promote the primary live materialized drift case (`Q100104196|P166`, `2277985537 -> 2277985693`) into repo-stable fixtures and review docs.
- [x] Promote a second confirmed live drift case (`Q100152461|P54`, `2456615151 -> 2456615274`) into the pinned repo pack.
- [x] Connect the new deterministic lexer/entity bridge outputs to the existing
  external-ref/entity substrate so seeded refs (`UN`, `UNSC`, `ICC`, `ICJ`)
  are persisted as linked entities without polluting canonical lexeme identity.
  Curated batch emission plus CLI upsert roundtrip coverage now exist.
- [ ] Expand the DB-backed deterministic bridge substrate only where corpus
  yield justifies it, keeping open-world Wikidata ambiguity resolution outside
  the lexer. Current v1 slice covers seeded global bodies plus the first
  GWB-oriented U.S. court/body set (`U.S. Supreme Court`, `U.S. Senate`,
  `House of Representatives`, `CIA`, `FBI`).

## Medium-Term Targets
- [ ] Add jurisdiction-aware GWB action review as a test target: be able to assess George W. Bush timeline actions under pinned U.S. law and Australian law, with U.S. law first.
- [ ] Build a U.S.-law seed set for GWB covering relevant actions, proceedings, and court/hearing material so specific events can be pinned to authoritative legal sources before broader cross-jurisdiction comparison.
- [ ] Import a reviewed deterministic bridge slice for the remaining GWB U.S.
  bodies/courts that are now lexically recognized but not yet QID-backed in the
  seeded bridge substrate (for example `Department of Defense` and the Sixth
  Circuit / district-court lane once the reviewed slice is pinned).
- [ ] Fix `scripts/migrate_wiki_timeline_to_itir_db.py` import-path assumptions
  so the eager rewrite/backfill command works directly without the current
  one-off package-path shim.
- [x] Normalize canonical structural atoms for DB dedupe, starting with the
  high-yield legal kinds (`case_ref`, `section_ref`, `act_ref`, `paragraph_ref`)
  and then layering in `institution_ref` / `court_ref` where useful.
  `VersionedStore` dictionary tables and root wiki-timeline DB atom tables now
  persist the high-yield structural kinds; `article_ref` and `instrument_ref`
  are now included as well.
