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
- [ ] Consolidate the docs around the extraction/enrichment boundary so the
  contract is explicit everywhere: local tokenizer/parser (`spaCy` dependency
  harvesting included) may provide deterministic structural evidence for
  relation inference, while Wikidata remains downstream enrichment/checking and
  never canonical token identity.
- [x] Expand the reviewed bridge slice with the next high-yield GWB U.S.
  additions: `Department of Defense` and the `United States Court of Appeals
  for the Sixth Circuit` are now pinned and imported into the shared bridge DB.
- [ ] Keep the reviewed bridge slice growing only through pinned, auditable
  entries. Immediate next reviewed additions are `United States Department of
  Defense` and `United States Court of Appeals for the Sixth Circuit`, plus any
  district-court alias variants that remain low-ambiguity after review.
- [ ] Import a reviewed deterministic bridge slice for the remaining GWB U.S.
  bodies/courts not yet present in the live bridge slice after the current sync
  (district-court lane variants and any additional reviewed executive/judicial
  bodies).

## Medium-Term Targets
- [ ] Add jurisdiction-aware GWB action review as a test target: be able to assess George W. Bush timeline actions under pinned U.S. law and Australian law, with U.S. law first.
- [ ] Build a U.S.-law seed set for GWB covering relevant actions, proceedings, and court/hearing material so specific events can be pinned to authoritative legal sources before broader cross-jurisdiction comparison.
- [ ] Move the initial GWB U.S.-law linkage seed from checked-in JSON into a
  shared import/query path once the reviewed scope is stable. Current plan is
  documented in `docs/planning/gwb_us_law_linkage_seed_20260307.md`.
- [ ] Keep chat-derived corpora isolated from canonical `itir.sqlite` until an
  explicit retention/redaction policy exists for SB/ITIR/TIRC integration.
  Current bounded test path is `.cache_local/itir_chat_test.sqlite` with hashed
  thread IDs only.
- [ ] Keep personal archive–derived test DBs (`itir_chat_test.sqlite`,
  `itir_messenger_test.sqlite`, similar local experiment stores) local-only and
  never promote them into canonical/shared repo artifacts or checked-in DBs.
- [x] Expand isolated chat test reporting beyond `_ref` counts. The current
  report now includes full kind breakdowns, structural-kind counts, top
  structural atoms, and structural-atom dedupe counts in
  `.cache_local/itir_chat_test.sqlite`.
- [x] Add richer structural reporting so chat/context corpora surface:
  top reused atoms, per-kind atom tables, interlinked/co-occurring atoms, and
  bounded example snippets rather than only aggregate counts.
- [x] Add a second deterministic operational/discourse structure lane for
  chat/dialogue, shell/command, and transcript-style patterns without changing
  the legal lexer.
- [ ] Extend the operational/discourse lane beyond the current regex-level v1:
  reduce false positives further, add better shell/session segmentation, and
  expand transcript/hearing-specific markers against real corpus files.
- [ ] Add a deterministic speaker-inference layer for transcript/message corpora
  only when there is reliable extra evidence (known participant set, coalesced
  disagreement structure, or reviewed entropy/disagreement heuristics). Do not
  infer speakers from subtitle-only timing ranges alone.
- [x] Write the deterministic speaker-inference v1 design note before
  implementation. See `docs/planning/speaker_inference_v1_20260307.md`.
- [ ] Decide whether Messenger/Facebook archive ingestion should graduate from
  isolated test DBs into a stable connector; current bounded importer is test
  only and still needs stronger system-row filtering policy.
- [x] Tighten bounded Messenger/Facebook importer filtering with deterministic
  keep/drop reason categories and per-run filter stats.
- [x] Add a deterministic Messenger test DB report command instead of relying
  on ad hoc Python summaries. `scripts/report_messenger_test_tokenizer_stats.py`
  now reports structure metrics plus kept/dropped filter counts.
- [x] Import a reviewed deterministic bridge slice for the current high-yield
  GWB U.S. bodies/courts in the seeded bridge substrate, including
  `Department of Defense` (`Q11209`) and the Sixth Circuit (`Q250472`).
- [ ] Extend the reviewed deterministic bridge slice further for remaining
  district-court / executive variants once corpus yield justifies the added
  aliases.
- [ ] Add a side-by-side corpus comparison summary artifact for
  chat/context/transcript runs so `--by-source` output is easier to review than
  the raw JSON dump. Initial compact summary is now emitted by
  `report_structure_corpora.py`; next step is polishing it into a more stable
  review artifact.
- [x] Fix `scripts/migrate_wiki_timeline_to_itir_db.py` import-path/runtime
  assumptions so the eager rewrite/backfill command works directly against the
  shared root DB.
- [x] Drive canonical wiki-timeline residual JSON toward zero for route/report
  critical storage. Event/step/object/list tails now persist through typed
  path/value tables and the refreshed GWB storage report shows `0` residual
  blob bytes.
- [ ] Do not chase "lossless reconstruction" of unused legacy JSON export
  shapes as a storage goal. Only normalize/preserve fields that matter for
  route parity, queryability, reporting, or audit semantics; explicitly delete
  or ignore dead tails instead of carrying them forward as canonical DB blobs.
- [x] Normalize canonical structural atoms for DB dedupe, starting with the
  high-yield legal kinds (`case_ref`, `section_ref`, `act_ref`, `paragraph_ref`)
  and then layering in `institution_ref` / `court_ref` where useful.
  `VersionedStore` dictionary tables and root wiki-timeline DB atom tables now
  persist the high-yield structural kinds; `article_ref` and `instrument_ref`
  are now included as well.
