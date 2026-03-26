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
- [x] Expand the DB-backed deterministic bridge substrate only where corpus
  yield justifies it, keeping open-world Wikidata ambiguity resolution outside
  the lexer. Current v1 slice covers seeded global bodies plus the first
  GWB-oriented U.S. court/body set (`U.S. Supreme Court`, `U.S. Senate`,
  `House of Representatives`, `CIA`, `FBI`) and now includes reviewed
  district-court alias variants (`U.S. district courts`, `US district courts`,
  `United States district courts`, `federal district courts`,
  `federal trial court`).
- [x] Consolidate the docs around the extraction/enrichment boundary so the
  contract is explicit everywhere: local tokenizer/parser (`spaCy` dependency
  harvesting included) may provide deterministic structural evidence for
  relation inference, while Wikidata remains downstream enrichment/checking and
  never canonical token identity. See
  `docs/planning/extraction_enrichment_boundary_20260307.md`.
- [x] Add a bounded Wikidata mereology/parthood design note for the current
  Niklas / Ege / Peter lane, focused on typed/disambiguated parthood
  (`class-class`, `instance-instance`, `instance-class`, inverse validity vs
  redundancy) rather than generic ontology repair. See
  `docs/planning/wikidata_mereology_parthood_note_20260307.md`.
- [x] Decide which parts of the existing DASHI-style epistemic/projection
  formalism are safe to reuse for Wikidata mereology diagnostics without
  collapsing the bounded control-plane work into an ontology-fix proposal.
  Decision captured in
  `docs/planning/wikidata_mereology_parthood_note_20260307.md`.
- [x] Add a bounded Wikidata property/constraint pressure-test note covering:
  financial-flow/timeseries modeling, subset-vs-total quantity representation,
  graph/report surfaces, and practical loaded-property questions (`supports`
  vs `P366`) as deterministic ontology diagnostics rather than ad hoc side
  discussions. See
  `docs/planning/wikidata_property_constraint_pressure_test_20260307.md`.
- [x] Define a review trigger for historical rewind checks on pinned Wikidata packs
  (e.g., confirmed-case disappearance, material severity flips, or focused
  property regressions) to decide when historical slices should be compared
  instead of only using the newest pinned snapshot.
- [x] Add a light diagnostic note on label harmonization signals (`type of XXX`
  vs `XXX subclass` and related variants) so user-facing naming inconsistency
  can be reported without treating labels as ontology truth. Captured in
  `docs/planning/wikidata_property_constraint_pressure_test_20260307.md`.
- [x] Expand the reviewed bridge slice with the next high-yield GWB U.S.
  additions: `Department of Defense` and the `United States Court of Appeals
  for the Sixth Circuit` are now pinned and imported into the shared bridge DB.
- [x] Keep the reviewed bridge slice growing only through pinned, auditable
  entries. The previously queued additions (`United States Department of
  Defense`, `United States Court of Appeals for the Sixth Circuit`, and the
  low-ambiguity district-court alias variants) are now imported.
- [x] Import a reviewed deterministic bridge slice for the remaining GWB U.S.
  bodies/courts not yet present in the live bridge slice after the current sync
  (district-court lane variants now imported; additional executive/judicial
  additions remain review-gated).
- [x] Add checked and dense Wikidata review artifacts above the structural
  handoff so the lane exposes review items, source review rows, unresolved
  clusters, cues, provisional rows, and bundle queues rather than only a
  status/handoff slice.
- [x] Add checked and broader GWB review artifacts above the existing checked
  public handoff and broader corpus checkpoint so the lane exposes the same
  operator-facing review geometry as AU/Wikidata.
- [x] Add a normalized cross-lane summary block for AU, Wikidata, and GWB so
  workload and ranking metrics become directly comparable rather than only
  shape-compatible.
- [ ] If external Wikimedia funding becomes operationally relevant for the
  Wikidata lane, keep a small maintained funding/watchlist note sourced from
  official online grant pages rather than treating "active Wikidata grants" as
  an implicit stable repo-local list. Current framing/spec note:
  `docs/planning/wikimedia_grant_framing_20260326.md`.
- [ ] If external Wikimedia funding becomes active, sample 2-3 funded and 2-3
  rejected Wikimedia proposal pages and compare the final wording against the
  current bounded Rapid Fund surfaces:
  `docs/planning/wikimedia_rapid_fund_draft_20260326.md` and
  `docs/planning/wikimedia_bounded_demo_spec_20260326.md`.
- [ ] If Wikimedia proposal work becomes active, translate
  `docs/planning/wikimedia_rapid_fund_draft_20260326.md` into the actual
  Wikimedia Meta/Fluxx field structure, preserving its documented evaluation
  metrics, acceptance criteria, and reviewer-facing bounded demo scope.
- [ ] If Wikimedia proposal work becomes active, confirm the named people used
  for the already-chosen reviewer route:
  preferred `1-2` Wikidata/ontology-adjacent reviewers, fallback `1-2`
  technically adjacent reviewers.
- [ ] If the attributed entity-kind appendix is kept in the submission pack,
  lock the exact revision-locked article snapshots used for that appendix
  before submission.
- [ ] Before any Wikimedia submission, run one attribution pass over the
  bounded demo pack so each foregrounded case is classified as:
  repo-built surface, attributed example, or method-lineage credit. Current
  matrix:
  `docs/planning/wikimedia_demo_attribution_matrix_20260326.md`.
- [ ] Before any Wikimedia submission, run one final wording pass against
  `docs/planning/wikimedia_prior_work_and_originality_note_20260326.md` so no
  sentence implies reproduction, parity, or first discovery beyond what the
  repo docs actually support.
- [ ] Only after the normalized metric block is stable, extract shared
  ranking/workload primitives and a shared review-core layer from the current
  AU/Wikidata/GWB adapter-local builders.
- [ ] Add one packaging/UX note that distinguishes private-user surfaces from
  institutional reporting surfaces so future Mirror/commercial drafts do not
  silently default to institution-only language or overstate authoritative
  outputs for personal users.
- [ ] Extend the implemented private-user day-to-escalation lane beyond the
  first bounded
  CLI/artifact contract in
  `docs/planning/personal_handoff_bundle_contract_20260326.md`:
  add richer live/export-backed chat/day ingest adapters plus stronger
  selective redaction/scoped export for legal, clinical, advocacy, or
  regulatory handoff beyond the current bounded JSON, repo-local sample-DB,
  direct Messenger-export, anonymous Google public-source, and first
  OpenRecall-backed adapters.
- [ ] Extend the first metadata-only protected-disclosure envelope mode:
  add whistleblower-specific live intake/import adapters and dedicated
  workflow/UI surfaces beyond the current metadata-only contract, which now
  includes recipient allowlisting, disclosure-route gating, and identity-
  minimization controls.
- [ ] Publish an explicit provenance-only integrator contract:
  SDK/API-oriented JSON/export contract docs and at least one fixture-backed
  consumer path, rather than relying on implicit review-artifact stability.
- [ ] Extend the contested-narrative response packet beyond sentence-role heuristics:
  add proposition-component decomposition for actor/action/object/time plus
  scoped response binding for denial, admission, qualification, consent,
  authority, necessity, and characterization dispute on top of
  `docs/planning/contested_narrative_response_packet_contract_20260326.md`.
- [ ] Add a community/disability support intake surface:
  bounded intake schema plus role-scoped export/view contracts above the
  current generic bundle/summary artifacts.
- [ ] Add an annotation/QA workbench layer over the existing review queues:
  abstain/inter-rater handling, disagreement visibility, and deterministic
  export semantics.
- [ ] Add a field inspection/offline-capture lane:
  photo/checklist capture, sync-gap metadata, and regulator/insurer export
  fixtures.
- [ ] Add a research/publication adapter lane:
  lab-note/research import plus publication-safe export with exclusions and
  provenance preserved.

## Medium-Term Targets
- [x] Adopt `sensiblaw.interfaces.shared_reducer` as the explicit supported
  cross-product reducer surface and move SB/TiRC/ITIR consumers onto it
  instead of relying on internal `src.text.*` imports or opaque fixture-only
  boundary assumptions.
- [ ] Track the resolved thread `QG Unification Proofs`
  (`69c27a0a-ed74-839c-8a57-3c184c28f88e` / canonical
  `f20d9304aae805879a1f934b71443bd2c80ac19b`) as a cross-project formalization
  boundary reference:
  - preserve the proposed `DA51 (empirical) → SL (canonical structure) → Agda (formal proof)` contract shape
  - preserve the `DA51Trace` fields (`da51`, `exponents`, `hot`, `cold`, `mass`, `steps`, `basin`, `j_fixed`)
  - note that this remains non-authoritative and private until JMD confirms any
    additional mapping context; do not publish private mapping details.
  - implement minimal prototype and adapter stubs in `src/qg_unification.py`.
- [x] Move to phase-1 adapter wiring once external adapter approvals are explicit:
  first DA51-like staged input -> `TraceVector` -> typed dependency envelope.
  - Added stage-2 staged artifact bridge output in
    `SensibLaw/scripts/qg_unification_stage2_bridge.py` (persisting run-id
    keyed artifacts).
  - Added deterministic fixture payloads for replayable boundary checks:
    - `SensibLaw/tests/fixtures/qg_unification/da51_valid_demo.json`
    - `SensibLaw/tests/fixtures/qg_unification/da51_invalid_short_exponents.json`
  - Added fixture-backed smoke/stage-2 runners so the same payload can be
    replayed through stage-1 and stage-2 paths.
  - Verified fixture-backed stage-2 output end-to-end:
    - artifact JSON emitted in caller-selected `--out-dir`
    - `qg_unification_runs` row persisted when `--db-path` is supplied
- [x] Add cross-product adapter consumers one path at a time:
  - added a first-path read-model adapter to persist staged QG runs into an
    ITIR-facing DB table:
    - `SensibLaw/scripts/qg_unification_to_itir_db.py`
    - `--bridge-db` + `--run-id` + `--itir-db` + `--dry-run`
    - data lands in `qg_unification_runs` using deterministic upsert semantics
  - added TiRC transcript/capture adapter sink:
    - `SensibLaw/scripts/qg_unification_to_tirc_capture_db.py`
    - creates transcript-like session/utterance rows in destination DB
    - deterministic run-id mapped records in `qg_tirc_capture_runs`,
      `qg_tirc_capture_sessions`, and `qg_tirc_capture_utterances`
  - next path: ITIR-facing UI/report producers needing canonical refs.
- [ ] Bridge the new random-page general-text timeline readiness harness into
  the canonical fact-intake observation/event seam. The current harness should
  prove `snapshot -> timeline candidates -> AAO events`; the next step is a
  deterministic sender from that output into Mary-parity observation/event
  storage rather than stopping at readiness scoring.
- [ ] Keep the adapter thin and SL-owned:
  no competing canonical identity store, no semantic authority transfer, and
  no local fallback path silently promoted to canonical.
- [ ] Add jurisdiction-aware GWB action review as a test target: be able to assess George W. Bush timeline actions under pinned U.S. law and Australian law, with U.S. law first.
- [x] Build a reviewed U.S.-law seed set for GWB covering relevant actions,
  proceedings, and court/hearing material so specific events can be pinned to
  authoritative legal sources before broader cross-jurisdiction comparison.
  Current seed is expanded beyond the original starter pack and checked in at
  `SensibLaw/data/ontology/gwb_us_law_linkage_seed_v1.json`.
- [x] Move the reviewed GWB U.S.-law linkage seed into a shared import/query
  path. Shared DB tables, deterministic import/run/report tooling, and receipt
  storage now exist; current plan/status is documented in
  `docs/planning/gwb_us_law_linkage_seed_20260307.md`.
- [x] Tighten the GWB U.S.-law linkage matcher so broad cues like `Congress`,
  `Iraq`, `veto`, and `Supreme Court` need stronger co-signals before low-score
  matches are promoted, while keeping ambiguous candidates visible in receipts.
  This is a promotion-threshold task, not a ban on broad mention extraction.
  Broad-cue-only cases may now remain visible as low-confidence matched/candidate
  output when they win unambiguously, but they no longer inflate medium/high
  confidence without stronger non-broad receipts.
- [x] Add a first deterministic GWB semantic layer on top of the reviewed
  U.S.-law linkage lane: unified entity spine, office-holding rows,
  mention-resolution artifacts, event roles, relation candidates, and promoted
  edge-first semantic relations. Current status is documented in
  `../docs/planning/gwb_semantic_phase_v1_20260307.md`.
- [x] Freeze the GWB semantic storage shape around the unified entity spine,
  actor/office split, mention-resolution artifacts, and edge-first
  `relation_candidate` -> `semantic_relation` progression before widening the
  predicate set further.
- [x] Extend the GWB semantic layer beyond the initial promoted predicates
  (`nominated`, `confirmed_by`, `signed`, `vetoed`) into stronger review and
  litigation relation coverage without collapsing noisy cue-only events into
  canonical relations. Current deterministic coverage now includes
  `ruled_by`, `challenged_in`, and `subject_of_review_by`.
- [ ] Keep the semantic v1.1 spine frozen while pressure-testing it against GWB:
  unified `entity`, first-class `mention_resolution`, `event_role ->
  relation_candidate -> semantic_relation`, and receipt-derived confidence
  should be exercised before adding more special cases.
- [ ] Migrate the current bounded GWB/AU/transcript predicate heuristics toward
  the shared slot/rule/promotion metadata substrate documented in
  `docs/planning/semantic_rule_slots_and_promotion_gates_20260308.md`.
  Shared rule/slot/promotion metadata now exists, promotion is policy-backed,
  and rule-family receipts should now be present on emitted candidates; the
  remaining work is tightening confidence derivation against shared policy
  minima/evidence requirements and only then deciding whether selector
  execution should move beyond profile-local code. Keep any such migration
  incremental and without breaking the event-scoped semantic spine.
- [ ] Revisit the shared selector-interpreter question only after the new
  policy-backed promotion path and rule-family receipts have been pressure-
  tested across GWB/AU/transcript corpora. Current decision is explicit defer:
  selectors remain shared metadata, execution remains profile-local.
- [ ] Keep `Bush administration` and similar discourse/political labels
  non-canonical by default until a reviewed concept/administration entity layer
  exists. Do not silently merge them into person or office actors.
- [ ] Keep title-only ambiguous mentions such as `the President` and `the
  court` abstained until office/forum context is strong enough to resolve them
  deterministically.
- [x] Add the three small deterministic SL -> SB boundary integration tests
  that likely close most current reducer-boundary risk:
  segmentation preservation, canonical ID preservation, and no summary
  injection.
- [ ] Keep SB/TiRC workflow wording explicit: SB only uses/extends SL-owned
  lexer/compression outputs and must not drift into legal-semantic authority.
  Legal-labelled fixtures at the SB boundary should be treated as opaque
  SL-origin canonical payloads only.
- [x] Align SB and SL docs on the same boundary statement: SB is a personal
  state compiler feeding TiRC/ITIR and may use/extend SL-owned
  lexer/compression outputs without acquiring semantic authority.
- [ ] Use the Australian corpus fixtures (`Mabo`, `House v The King`,
  `Plaintiff S157`, `Native Title (NSW) Act 1994`) as the required semantic
  cross-test source for the frozen v1.1 entity/role/relation shape before
  widening it.
- [x] Start a bounded freeform/transcript semantic proving lane after the AU
  legal fixtures to pressure-test the same frozen
  `entity -> mention_resolution -> event_role -> relation_candidate ->
  semantic_relation` shape against noisier text. Keep extraction broad where
  useful, but keep promotion and speaker/actor resolution conservative and
  abstention-friendly. Current v1 persists speaker/mention/event-role artifacts
  plus candidate-only `replied_to` relations; see
  `../docs/planning/transcript_semantic_phase_v1_20260308.md`.
- [x] Extend the transcript/freeform semantic lane beyond the first
  speaker/event-role proving pass so it becomes the profile-neutral SL
  baseline for human text: broad source-local freeform entity extraction now
  exists, explicit non-legal affect/state cues can emit candidate-only
  `felt_state` relations, and legal semantics remain gated to explicit
  AU/GWB/legal entrypoints.
- [x] Tighten the generalized transcript/freeform entity heuristics so obvious
  non-entity titlecase tokens stay abstained without sliding back into
  legal-by-default behavior or shrinking broad human-text coverage. Current
  bounded gates keep contextual single-token person/place surfaces such as
  `Picasso` / `Brisbane`, while dropping obvious titlecase noise such as
  `Thanks`, `Today`, and role/system labels from general entity extraction.
- [ ] Add stronger general non-legal participant/context roles to the
  transcript/freeform lane (beyond `speaker`, `subject`, `mentioned_entity`,
  `theme`) and pressure-test them against journal/transcript corpora before
  promoting any new relation family. Align this with the existing
  actor/event-role contracts already used elsewhere in the repo rather than
  introducing a transcript-only ad hoc role taxonomy. Archive-backed summary:
  `../docs/planning/archive_actor_semantic_threads_20260308.md`.
- [x] Add the first bounded explicit social-relation slice to the
  transcript/freeform lane without widening into open-world social inference.
  Current deterministic v1 covers named explicit kinship/friendship statements
  plus explicit guardian/care surfaces only (`sibling_of`, `parent_of`,
  `child_of`, `spouse_of`, `friend_of`, `guardian_of`, `caregiver_of`), keeps
  them candidate-only, and may attach `related_person` event-role context
  where the paired actor is explicit in the same text span.
- [x] Normalize transcript/freeform care relation naming so canonical
  predicates stay relation-style and tense-neutral. Current choice is
  `caregiver_of`; observed surfaces such as `cared for` / `cares for` remain
  in receipts only.
- [x] Add a compact transcript semantic summary artifact focused on relation
  review. The bounded summary now reports candidate/promoted counts by
  predicate, cue-surface counts, and an explicit note when all social/care
  predicates remain candidate-only.
- [x] Move semantic workbench `text_debug` payload shaping out of
  `itir-svelte` and into Python report producers. Current report builders now
  own tokenization, anchor provenance, relation-family metadata, and
  confidence-derived display opacity for transcript/GWB/AU semantic workbench
  rendering.
- [x] Add a shared producer-owned `review_summary` artifact to GWB/AU/transcript
  semantic reports so predicate counts, cue-surface counts, and `text_debug`
  coverage/exclusion totals are comparable across corpora without inspecting
  raw report JSON.
- [x] Extend producer-owned `text_debug` anchors with `charStart`, `charEnd`,
  and `sourceArtifactId` so the next graph/document linking step has a real
  shared span contract instead of token-only render helpers.
- [x] Use the producer-owned `text_debug` span contract in the semantic report
  workbench for event-local cross-highlighting. Current v1 keeps the separate
  source-document slot explicit about unavailable source text rather than
  inventing a fake full-document surface.
- [x] Extend transcript/freeform reports with grouped source-document payloads
  and source-level event spans so the semantic workbench can cross-highlight
  into a real source-text view without re-deriving offsets in TS.
- [x] Emit grouped timeline-source payloads and source-level event spans for
  GWB/AU from the normalized wiki timeline store so the semantic workbench
  source-document viewer stops being transcript-only.
- [x] Add an append-only semantic review-feedback seam for the workbench.
  Current `/graphs/semantic-report` submissions now persist append-only DB
  review rows keyed by source/run/event/relation/anchor refs instead of
  rewriting semantic tables in place.
- [x] Add a bounded transcript/freeform `mission_observer` artifact for SB-safe
  mission/follow-up overlays. Current v1 is deterministic and local:
  explicit task/follow-up cues, source-local referent backtracking, deadline
  carry-forward when grounded, and abstention on unresolved follow-ups.
- [x] Move semantic review submissions out of local JSONL and into append-only
  `itir.sqlite` tables (`semantic_review_submissions` +
  `semantic_review_evidence_refs`) so the workbench review seam is DB-first.
- [ ] Pressure-test the transcript/freeform `mission_observer` lane against
  more chat/message corpora before widening cue coverage or letting SB derive
  stronger reductions from it.
- [x] Add a bounded public-media narrative corpus fixture for transcript/media
  validation, using FriendlyJordies as the first named public test case. The
  first slice now exists as `SensibLaw/demo/narrative/friendlyjordies_demo.json`
  plus the bounded `narrative_compare.py` producer and comparison workbench.
- [ ] Add a narrative-validation review mode for transcript/media corpora:
  internal consistency checks, source-local proposition extraction, explicit
  external corroboration/support/conflict refs, and abstention when the source
  remains unresolved.
- [x] Add a competing-narratives comparison read model for SensibLaw so two
  source narratives can be compared by shared facts/propositions,
  source-specific propositions, disagreement markers, predicate/flow
  differences, and explicit receipts rather than silent merging. Current first
  slice is a bounded fixture-first producer/workbench pair, not the later
  ingress-backed review mode.
- [x] Persist the transcript/freeform `mission_observer` artifact canonically
  in normalized `itir.sqlite` mission tables before exporting/reviewing it as a
  report payload. Current storage is `mission_runs`, `mission_nodes`,
  `mission_edges`, `mission_evidence_refs`, `mission_observer_overlays`, and
  `mission_overlay_refs`.
- [x] Add the first fused mission-lens substrate on top of the persisted
  mission observer lane: seed ITIR-owned planning nodes/deadlines from mission
  rows, build an actual-vs-should artifact against SB dashboard data, and
  expose bounded planning authoring without changing SB’s core doctrine.
- [x] Add a reviewed actual-to-mission mapping lane on top of the fused mission
  lens so concrete SB activity rows can be linked to planning nodes in
  `itir.sqlite` (`mission_actual_mappings`) instead of relying only on lexical
  fallback when drift/accounting is reviewed.
- [ ] Tighten automatic actual-to-mission mapping beyond the current reviewed +
  lexical bridge before treating mission drift as a stronger accounting
  surface.
- [ ] Bring the wiki revision monitor lane up to the same functional standard
  as the stronger suite pipelines before prioritizing GUI integration:
  - add query-first helpers/read models over latest runs, changed articles,
    severities, and issue-packet summaries instead of relying on raw
    `result_json` blobs alone
  - keep producer-owned report surfaces explicit so other lanes can consume
    revision artifacts without re-deriving monitor logic
  - preserve the dedicated runner/state-DB posture; this is a standards/
    interoperability task, not a demand to fold the lane into `itir-svelte`
- [x] Add an OpenRecall observer integration v1 lane:
  - vendored `openrecall/` SQLite captures now import into `itir.sqlite` via a
    bounded append-only importer and normalized capture tables/read models
  - capture provenance (`captured_at`, app/window title, OCR text, source DB
    path, screenshot refs) is preserved and ingest remains observer-class only
  - imported captures now appear as a mission-lens actual-side source kind and
    as source-local text units for semantic/transcript reuse
  - raw OCR/capture rows remain non-authoritative on ingest
- [ ] Follow up on OpenRecall v1:
  - stabilize or bypass the inconsistent vendored live-capture path before
    relying on OpenRecall as a routine upstream source
  - decide whether capture-derived observer overlays should ever cross into SB,
    and only through ITIR-normalized payloads
  - defer GUI-first OpenRecall browsing until the importer/read-model seam is
    proven stable
- [x] Add the first NotebookLM metadata/review parity slice as a neutral
  producer/query/read-model seam instead of treating `notes_meta` as a fake
  activity ledger. Current v1 now exposes NotebookLM observer date/notebook/
  source/artifact summaries plus recent-event queries and source-summary
  `TextUnit` projection for downstream structure/semantic reuse.
- [ ] Keep NotebookLM metadata-first until a separate interaction-grade capture
  contract exists. Do not upgrade `notes_meta` snapshots into waterfall/
  timeline activity parity or stronger mission actual-side accounting without
  explicit NotebookLM ask/chat/note/artifact/session events.
- [x] Implement the first additive NotebookLM interaction lane without claiming
  activity/session parity:
  - raw capture families: `conversation_observed`, `note_observed`
  - separate normalized signal: `notebooklm_activity`
  - bounded query/read-model helpers and JSON CLI
  - source-local preview `TextUnit` projection
  - keep outputs under `runs/<date>/outputs/notebooklm/`; do not fold them
    into `logs/notes` or dashboard waterfall/timeline accounting yet
- [ ] Decide how much richer NotebookLM interaction capture should get before
  any dashboard or mission-lens activity/session integration:
  - whether conversation-history observations are sufficient, or whether the
    later lane must capture true ask/request/result and note-edit events
  - whether the interaction lane should stay review/query-only until stronger
    timestamps and dedupe semantics exist
- [ ] Widen the bounded proposition-layer v1 beyond current HCA-first
  `... against ...` reasoning idioms and factual scaffolding:
  - cited-authority subgroup handling (`majority in Lepore`, similar)
  - richer proposition-link families beyond current bounded
    `attributes_to` comparison support
  - broader attribution wrappers beyond current bounded
    `said/argued/submitted/reported/held/showed that`
  - proposition-to-proposition links usable by competing-narratives comparison
  Keep canonical storage on `predicate_key + negation/stance + typed arguments`
  rather than operator syntax.
- [ ] Mine the high-signal local archive threads into first-class repo notes so
  actor/role architecture does not stay trapped in chats. Priority threads:
  `Actor table design` (`21f55daa80206517e38f8c0fa56ee9bb2db8a9a0`),
  `Actor Model Feedback` (`691d79376cb653e7170ea6c200a0a1d0a34bec6b`),
  `Milestone Slice Feedback` (`1802fc3d13a0ad01ad95cef07eeaae9c16c22bed`),
  `Taxonomising legal wrongs` (`74f6d0e08de82556df95c6ab1edb51557fede4fa`),
  `SENSIBLAW` (`4d535d3f33f54b1040ab38ec67f8f550a0f69dce`), plus the currently
  untitled high-hit archive threads `dbcfb20d67213216c7aa02ed8493ae21fd39730d`
  and `dff2e608e358fe5ed5cf1d0376a36ff8a87a6f2d`.
- [ ] Decide which archive-derived actor-model pieces should actually re-enter
  the active semantic schema family after the current comparison pass in
  `../docs/planning/actor_semantic_db_design_from_archive_20260308.md`.
  Current explicit gaps versus the broader archive design are:
  persistent alias registry, merge audit, governed event-role vocabulary, and
  actor detail/annotation extension tables.
- [x] Re-introduce the first archive-backed identity-governance pieces without
  replacing the frozen semantic spine: shared `actors`, `actor_aliases`,
  `actor_merges`, and `event_role_vocab` now exist, and actor-like semantic
  entities map onto the shared actor layer via `semantic_entities.shared_actor_id`.
  This keeps alias persistence / merge audit / role governance shared across
  AU, GWB, and transcript lanes while leaving actor detail/profile extensions
  deferred.
- [ ] Decide how aggressively the new shared `actor_aliases` layer should
  participate in deterministic matching. Current recommendation is
  conservative: keep it primarily as persisted registry/audit support plus
  seed-backed reuse, and only widen alias-driven matching if concrete corpus
  pressure shows lane-local matching is missing high-value recoverable actors.
- [ ] Decide whether any transcript/freeform relation family deserves
  medium/high promotion under the frozen semantic spine. Current `replied_to`
  and `felt_state` relations remain candidate-only, and the new explicit
  social-relation predicates (`sibling_of`, `parent_of`, `child_of`,
  `spouse_of`, `friend_of`, `guardian_of`, `caregiver_of`) also remain
  candidate-only.
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
- [x] Start the deterministic speaker-inference implementation with explicit
  receipts/abstention behavior over current transcript/message units. Current
  v1 supports explicit message headers, role prefixes, cautious `Q:/A:` mapping
  when known participants are supplied, and explicit abstention on timing-only
  subtitle ranges.
- [ ] Extend speaker inference from per-unit receipts to conservative
  multi-turn coalescence with explicit carry-over receipts and no silent
  speaker invention across conflicting evidence. Current implementation only
  covers single-gap `neighbor_consensus` carry-over when the same explicit
  speaker brackets an `insufficient_evidence` unit.
- [x] Write the deterministic speaker-inference v1 design note before
  implementation. See `docs/planning/speaker_inference_v1_20260307.md`.
- [ ] Decide whether Messenger/Facebook archive ingestion should graduate from
  isolated test DBs into a stable connector; current bounded importer is test
  only and still needs stronger system-row filtering policy.
- [ ] Tighten Messenger sender extraction so platform/system text cannot bleed
  into inferred speaker labels such as `speaker:facebookwe_didn_t_remove_the_ad`
  or similar contaminated forms in the speaker-inference report.
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
- [x] Add Messenger test DBs as first-class inputs to the shared structure
  comparison/report path instead of keeping them on an isolated report script
  only.
- [ ] Add a compact speaker-inference summary surface alongside the structure
  reports (assigned vs abstained, confidence tiers, dominant reason codes, top
  inferred speakers) for transcript/chat/message corpora. Initial JSON report
  now exists in `scripts/report_speaker_inference_corpora.py`; next step is a
  tighter review-oriented summary artifact.
- [x] Add a deterministic top-k relation-neighborhood report for
  chat/context/transcript corpora that combines parser-local dependency /
  co-occurrence evidence with reviewed bridge/Wikidata matches where a pinned
  slice exists. Implemented in
  `scripts/report_relation_neighborhoods.py`.
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
- [x] Align main SB and SL docs so the lexer/compression boundary is explicit:
  SB is a personal state compiler feeding TiRC/ITIR and may use/extend SL
  lexer/compression outputs without inheriting semantic/legal authority.
- [x] Add Australian semantic seed/report lane on the frozen semantic v1.1
  spine using:
  - Mabo [No 2]
  - Plaintiff S157/2002 v Commonwealth
  - House v The King
  - Native Title (New South Wales) Act 1994
- [x] Extend Australian semantic actor extraction beyond the first
  document-local participant patterns into deterministic legal-representative
  and office lanes.
- [x] Broaden Australian relation candidate coverage for review/litigation and
  doctrinal reasoning while keeping promotion conservative.
- [x] Tighten Australian legal-representative extraction beyond the first
  `SC/KC/QC` and `counsel for ...` deterministic surfaces. Current AU lane now
  uses a versioned lexical cue catalog with clause-local named-representative
  gating instead of creating synthetic role-label actors from cue text alone.
- [ ] Promote the AU legal-representation cue catalog from versioned repo data
  into a shared DB-backed lexical-rule substrate only if multiple
  jurisdictions/extractors need the same runtime shape. Do not widen semantic
  schema or ontology tables for cue storage.
