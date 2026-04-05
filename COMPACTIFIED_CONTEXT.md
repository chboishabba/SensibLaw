# COMPACTIFIED_CONTEXT

## Purpose
Compact snapshot of intent while aligning the new Zelph review-geometry parity
work with docs, TODOs, and changelog state.

## Current addendum (2026-04-05)
- refreshed archived-context lookup for the referenced ChatGPT thread:
  - online UUID:
    `69d1d8da-5c44-83a0-a69a-48b2336866be`
  - canonical thread ID:
    `a8d28b4c2a5caf03a05cb5ab357da933083782fc`
  - archived title:
    `Enshittification Failure Model`
  - source used:
    local DB via direct archive pull into `/home/c/chat_archive.sqlite`
  - main observed topics:
    broader failure-model discussion with pasted SensibLaw state, including
    the current product-gate / proposition-resolution naming seam
- governing decision for this turn:
  the refreshed thread does not materially change repo-facing intent; local
  docs remain the canonical planning surface
- ontology clarification now pinned:
  - product gate is a promotion-posture surface, not a proposition-resolution
    surface
  - current product-gate vocabulary:
    `promote | audit | abstain`
  - proposition-resolution vocabulary remains:
    `hold | abstain`
  - `no_promoted_outcomes` is a product-gate reason, not a replacement
    ontology
  - future normalization should preserve that boundary unless a deliberate
    full migration changes the product-gate contract across all consumers

## Current phase (2026-03-27)
Semantic-promotion parity is now the active cross-lane governance lane.

## Current phase addendum (2026-03-31)
- ontology enrichment is being forward-ported onto the normalized
  `src/ontology` surface rather than the older `src/sensiblaw/ontology`
  branch shape
- `#423` is the live candidate for that forward-port; `#422` remains a
  separate confidence-migration idea and is too stale to merge directly
- governing rule for this lane:
  provider-backed enrichment may add candidate lookup and interactive upsert
  helpers, but it must not fork a parallel ontology package or duplicate the
  current CLI architecture

Current addendum (2026-03-28):
- refreshed online context now pins two additional doctrine boundaries:
  - all-sources `FactBundle` / reconciliation is the broader direction above
    current `Observation` / `Claim` contracts; Wikidata remains a downstream
    projection/review lane rather than the canonical fact shape for all
    sources
  - sentiment/affect remains speaker/utterance-anchored candidate or overlay
    material; it is not a canonical legal-truth surface and should not expand
    into psychometric or dashboard-authority claims
- the Wikidata migration lane now has its first real text-side producer:
  - source schema:
    `schemas/sl.wikidata.climate_text_source.v1.schema.yaml`
  - runtime:
    `src/ontology/wikidata.py`
  - materializer hook:
    `scripts/materialize_wikidata_migration_pack.py`
  - bounded rule:
    explicit year/value climate lines only, revision-locked input only,
    output through `sl.observation_claim.contract.v1`, then additive bridge
    pressure only
  - current live target-selection result:
    `HSBC` / `Q190464` is not a valid lane target right now because it does
    not currently expose live `P5991`
  - next real artifact hunt should therefore pivot to already-pinned entities
    like `Q10422059` (`Atrium Ljungberg`) and `Q10403939`
    (`Akademiska Hus`)
  - first non-fixture artifact now exists:
    `data/ontology/wikidata_migration_packs/p5991_p14143_climate_pilot_20260328/climate_text_source_q10403939_akademiska_hus_scope1_2018_2020.json`
    built from official annual report excerpts for 2018, 2019, and 2020
  - first real bridge result:
    the artifact validates against `sl.wikidata.climate_text_source.v1`,
    yields `3` promoted observations / claims, and after the new temporal
    gating pass drives `split_pressure` on all `24` current `Q10403939`
    candidates
  - interpretation:
    this is the correct conservative outcome because the text slice is older
    scope-1 evidence while the current structured bundle is 2023 multi-scope
    data, so the bridge should surface dimensional mismatch rather than hard
    contradiction
  - next gap:
    add simple scope-tag carriage / matching before using real text evidence
    as support rather than only temporal-dimension pressure
  - next generalization boundary:
    source capture should become source-unit driven rather than PDF-driven
  - runtime move is now implemented:
    `sl.wikidata.climate_text_source.v1` remains as a backward-compatible
    legacy subtype, and a generic revision-locked `sl.source_unit.v1` plus a
    `SourceUnitAdapter` path now exists for PDF snapshot text and HTML
    snapshot text
  - broader abstraction note:
    the next higher formalism above current boundary objects is not just
    another shared interface; it is a typed composition system over boundary
    artifacts and governed morphisms
  - current decision:
    keep that as a docs-first planning note for now rather than introducing a
    shared runtime algebra prematurely
  - candidate concrete next layer, if runtime pressure later justifies it:
    `BoundaryArtifact.v1` + `Morphism.v1` + a bounded composition validator +
    a small readable transformation DSL
  - cross-system note:
    `Phi_meta` is already a shipped bounded executable layer; the next useful
    move there is a concrete `common_law <-> civil_law` example plus a bounded
    real-data prototype, not another abstract schema rewrite
  - track separation:
    the Wikidata climate lane and the cross-system legal lane now have
    different optimal next moves:
    - climate lane: `source_capture -> SourceUnit`
    - cross-system lane: bounded two-system prototype over promoted records

- 2026-03-28 ITIR / SensibLaw receipts-first compiler spine:
  - main decision:
    treat ITIR/SensibLaw as a receipts-first compiler with five explicit
    layers:
    source substrate -> deterministic extraction -> promotion -> reasoning ->
    public-action packaging
  - architectural center:
    promotion, not embeddings, graph ML, or public rendering
  - canonical truth rule:
    only promoted truth is canonical; graph and publish layers remain derived
    downstream consequences
  - downstream rule:
    public-facing outputs must stay receipt-backed and must not outrun the
    promoted proof base
  - next milestone:
    one bounded doctrine prototype emitting clause candidates with spans,
    promoted facts with abstentions, typed graph, proof tree, and one
    receipt-backed public-action artifact
- 2026-03-28 identity / trust alignment refinement:
  - main decision:
    the suite must not be treated as only a legal compiler; it is also a
    trust-preserving alignment layer between lived experience, evidence,
    formal rules, and actionable next steps
  - stronger requirement:
    convert fragmented lived experience into trustworthy, non-gaslighting
    legal and identity support without forcing full restatement from scratch
  - bounded internal lane:
    any identity/trust compiler surfaces remain user-sovereign,
    non-diagnostic, and non-canonical relative to promoted legal truth
  - lattice refinement:
    success now depends on legal validity, evidential validity, and
    trust-preserving interpretability together
  - milestone refinement:
    the first bounded doctrine prototype should prove both fact -> rule
    legibility and truth -> trust usability
- 2026-03-28 refreshed online thread sync:
  - title: `ZKP for ITIR SensibLaw`
  - online UUID: `69c7b950-daec-839d-89a9-8fd8e22c9136`
  - canonical thread ID: `31a47318f53b61cac9f82705e2595b1a08f9af66`
  - source used: `db` after direct UUID pull into `~/chat_archive.sqlite`
  - main decision:
    the receipts-first + trust-preserving architecture still holds, but the
    next maturity gap is operational readiness rather than more ontology
  - newly-sharpened gaps:
    missing service-level definitions, incident vs problem handling,
    measurable success criteria, and explicit system-boundary / handoff views
- 2026-03-28 standard service application model:
  - main decision:
    move from case-specific framing to one repeatable service application
    pattern for new scenarios
  - standard flow:
    intake -> evidence structuring -> identity/context modelling -> alignment
    -> obligation assignment -> output -> monitoring/escalation
  - standard control additions:
    standardized intake fields, mandatory obligation layer, one
    nonconformance grammar, and one comparable metric set across case families
  - adaptation rule:
    only rule sets, risk models, trust sensitivity, and SLA values should vary
    by case; the service structure itself stays constant
- 2026-03-28 everyday mode:
  - main decision:
    ordinary users should use the same architecture under a lighter operating
    mode rather than a separate product
  - mode shift:
    crisis/adversarial mode remains strict, formal, auditable, and
    enforceability-oriented; everyday mode becomes lighter, faster,
    suggestive, and confidence-building
  - output shift:
    everyday mode should bias toward next-best-action guidance rather than
    proof-heavy packaging
  - next design gap:
    add bounded switching criteria between crisis/adversarial mode and
    everyday/navigation mode
- 2026-03-28 case-type libraries + KPI model:
  - main decision:
    case handling should now be organized around fixed-shape service libraries
    rather than topic buckets only
  - first libraries:
    tenancy, abuse/accountability, medical/trauma-informed care,
    welfare/support
  - control decision:
    use one shared KPI language across libraries:
    service, quality, obligation, trust/usability, plus a small
    library-specific slice
  - next prototype rule:
    choose one concrete library and one minimal KPI slice rather than staying
    fully generic
- 2026-03-28 diagrams + mode-switching / UI / templates:
  - main decision:
    the suite now has repo-owned PlantUML definitions for the context,
    containers, standard flow, four case libraries, and obligation sequence
  - mode decision:
    one architecture, two bounded operating modes, with switching based on
    risk, time pressure, conflict level, evidence density,
    trust fragility, and user intent
  - product decision:
    ordinary-user UX should optimize for quick capture, fast orientation, one
    next-best action, and progressive depth rather than proof-heavy default
    views
  - stricter mode note:
    strict mode is explicitly tied to actor/time/fallback obligations,
    mandatory provenance, explicit uncertainty states, and escalation-ready
    handling
  - guardrails:
    no identity assertions without evidence, no moralizing language,
    no hidden assumptions, abstain when uncertain, local-first by default
  - template set:
    work/manager conversation, email/communication, tenancy friction,
    money/bills, health/appointments, personal planning, low-to-high conflict
  - KPI/control note:
    mode correctness, user overrides, first-pass usefulness, 24h action rate,
    tone-mismatch rework, retraumatization flags, escalation success,
    strict-mode obligation completion
  - C4 placement:
    mode is now documented as an explicit controller surface between
    trigger-detection input/alignment and obligation/output rendering rather
    than a hidden presentation toggle
  - consolidated product-spec note:
    the mode controller now has explicit inputs, outputs, deterministic
    selection rules, behavior profiles, and governance enforcement levels
  - obligation primitive:
    the documented core object is now:
    need, responsible actor, required action, deadline, status,
    evidence links, fallback actor, escalation rule
  - PlantUML extension:
    the architecture bundle now also includes explicit mode-controller
    alignment and everyday UX-flow diagrams, plus compact context/container,
    mode-selection, standard-flow, and obligation-lifecycle variants
  - summary reading:
    the suite is now documented as a controlled service that turns human
    situations into structured, actionable, accountable outcomes
  - next design rule:
    widen normal-user scope only after defining a bounded switch table and a
    small starter set of everyday templates
- 2026-03-28 production schema / dashboard / deployment pack:
  - main decision:
    the next production-facing contract layer now exists for entities,
    dashboards, and local-first deployment
  - entity decision:
    the first production entity set now explicitly includes case, evidence,
    atoms, identity/trust signals, gaps, obligations, outputs, review,
    audit, access, and mode state
  - dashboard decision:
    the monitoring/UI split is now:
    user dashboard, operations dashboard, governance dashboard
  - deployment decision:
    default local-first single-user runtime first, optional trusted sync
    second, restricted collaboration only as a later profile
  - first production-validation slice:
    validate local-first single-user case engine, truth-status states,
    obligation object, and dashboard surfaces before attempting full
    collaboration-platform scope
- the repo now has a bounded executable typed latent graph over promoted
  relation records:
  - runtime: `src/latent_promoted_graph.py`
  - schema: `schemas/sl.latent_promoted_graph.v1.schema.yaml`
  - focused coverage: `tests/test_latent_promoted_graph.py`
- current cross-system `Phi` output now composes directly with that graph
  slice:
  - top-level `latent_graphs` summaries are emitted in
    `sl.cross_system_phi.contract.v1`
  - mapping-level `mapping_explanation.latent_graph_refs` point back to the
    typed graph nodes/motifs for the mapped promoted records
- the bounded rule remains:
  graph structure is derived from promoted records and anchored provenance; it
  does not create an additional truth layer above promotion

Current status:
- first bounded feedback receipt receiver now exists in `itir.sqlite` via the
  fact-intake/read-model layer, with explicit separation between direct user
  evidence and `story_proxy` receipts through `feedback.receipt.v1`
- direct CLI receipt capture/import now exists over the same receiver via
  `scripts/query_fact_review.py`:
  `feedback-add` and `feedback-import`
- the remaining gap is better collector/operator ergonomics beyond raw CLI
  flags or hand-authored JSONL
- `follow.control.v1` now exists as the first shared cross-source operator
  control-plane contract in `src/fact_intake/control_plane.py`
- first concrete adopters are:
  - AU `operator_views.authority_follow`
  - generic fact-review `operator_views.intake_triage`
  - generic fact-review `operator_views.contested_items`
- the intended parity rule is now explicit:
  source families may differ in domain semantics, but they should converge on
  a shared queue/control-plane grammar (`hint -> receipt -> substrate ->
  conjecture -> operator queue`)
- contested claims use the central semantic candidate + tetralemma promotion gate
- GWB and AU semantic relation lanes emit the shared relation candidate contract
- transcript/SB semantic relation rows now emit the same central candidate and
  canonical promotion metadata
- Wikidata hotspot packs now emit a distinct hotspot-pack candidate contract
- mission observer overlays remain operational-state only and are explicitly
  not truth-bearing semantic promotion outputs

Current closure check:
- broader semantic parity validation should pass from the `SensibLaw/` cwd
  without relying on repo-root `PYTHONPATH` injection for mission-lens tests
- covered-lane CI/static enforcement now exists for the central promotion gate
  via `tests/policy/test_semantic_gate_enforcement.py`
- the remaining next-step class is deeper parser-backed structural basis in
  already-covered semantic lanes
- first follow-through on that basis work is now in place for relation lanes:
  relation basis requires an explicit subject/object/predicate spine, and the
  transcript lane now emits object/predicate receipts for `felt_state` and
  `replied_to` so those rows can stay structurally grounded without relying on
  weaker fallback cues
- contested semantic basis is also now less blunt:
  explicit predicate/component bindings can promote rows to `structural`, while
  lexical justifications remain the reason a row stays `mixed`
- covered semantic summaries now expose `semantic_basis_counts`, so the
  remaining `mixed`/`heuristic` shrinkage is directly measurable in report
  artifacts rather than only inferred from spot checks
- mission observer is now clearly SB/mission-lens scoped operationally, but it
  still requires a separate SL-reducer-backed candidate/promotion design
  before it should enter the canonical truth-bearing semantic family
- the repo's large JSON footprint is now explicitly classified in
  `docs/planning/json_artifact_boundary_20260327.md`:
  dominant JSON families are fixtures, demos, source/data seeds, and local
  caches rather than canonical runtime fact state
- `itir-svelte /corpora/processed/personal` is now DB-first for persisted
  `:real_` fact-review runs; checked-in demo-bundle JSON is no longer used to
  hydrate those runtime summaries
- affidavit review now has a narrow canonical persisted receiver in
  `itir.sqlite` for normalized runs/rows/facts via
  `persist_contested_affidavit_review(...)`
- JSON/markdown affidavit review artifacts remain derived projections; UI
  surfaces still need a follow-up pass to prefer the persisted lane
- authority retrieval workflow is now explicitly frozen as a docs-level rule:
  operator use must stay inside repo-owned seams
  (already-ingested/local artifact -> explicit AustLII URL if known ->
  JADE exact MNC when authorized -> deterministic `MNC -> AustLII case URL`
  derivation -> AustLII SINO -> local paragraph work), and ad hoc
  live probing outside that path is now treated as policy drift rather than a
  valid convenience shortcut
- deterministic AustLII URL derivation is now a promoted part of the known
  authority path:
  `austlii_case_url_guess(...)` is treated as a direct canonical case-URL
  construction step for known neutral citations, not as a heuristic search
- the repo now has a direct AustLII known-authority CLI seam:
  `sensiblaw austlii-case-fetch` accepts either a neutral citation or an
  explicit AustLII case URL, then performs local paragraph work and optional
  persisted authority-ingest receipt storage without using SINO
- bounded citation-follow now completes the documented AustLII chain:
  after JADE exact MNC and deterministic AustLII case-URL derivation, it uses
  SINO as the final bounded discovery step with strict exact-citation matching
  and abstains if no exact result is returned
- AU semantic/fact-review itself remains seed/linkage driven over normalized
  timeline payloads; it does not currently auto-invoke the AustLII/JADE
  fetch/follow seam during normal pipeline runs
- the first repo-owned operator seam for that workflow now exists:
  `sensiblaw austlii-search` can emit local paragraph-indexed excerpts from the
  fetched authority HTML via `--paragraph` / `--paragraph-window`, with
  fixture-backed tests and a live opt-in AustLII fetch/parse canary
- JADE is now at operator-path parity for the known-authority case:
  `sensiblaw jade-fetch` accepts a neutral citation or explicit JADE URL,
  resolves MNCs through the repo-owned `content/ext/mnc/...` contract, and can
  emit local paragraph-indexed excerpts via `--paragraph` /
  `--paragraph-window`, with fixture-backed tests and an opt-in live canary
- JADE now also has a secondary best-effort operator search seam:
  `sensiblaw jade-search` uses the public `/search/{term}` shell for one
  bounded search request, parses any visible server-rendered hits, appends a
  deterministic `/mnc/...` fallback hit when the query contains a neutral
  citation, and then performs fetch + local paragraph work through the same
  bounded receipt path
- the operator authority seam now also has a canonical persisted bounded
  receiver in `itir.sqlite`:
  `sensiblaw austlii-search --db-path ...`, `sensiblaw jade-fetch --db-path ...`,
  and `sensiblaw jade-search --db-path ...` persist an authority-ingest run
  header plus selected paragraph segments, with query access via
  `scripts/query_fact_review.py authority-runs` and `authority-summary`
- repo scope distinction:
  source-pack/HCA demo lanes already do bounded authority ingest/follow into
  downstream timeline/graph artifacts (`source_pack_manifest_pull.py` ->
  `source_pack_authority_follow.py`, plus `hca_case_demo_ingest.py`)
- the narrower statement is now:
  AU fact-review/semantic runtime remains seed/linkage-driven and does not
  auto-follow AustLII/JADE authorities during normal runs, even though
  adjacent AU/HCA ingest/demo lanes do; however, AU runtime now reuses
  persisted `authority_ingest` receipts by default as a semantic-context lane
  carrying a lightweight authority substrate summary and typed follow-needed
  conjectures, with an explicit opt-out for minimal runs
- the lightweight AU authority substrate now includes:
  source identity, selected paragraph numbers, selected segment previews/kinds,
  linked event sections, linked authority signals, extracted neutral citations
  / authority-term tokens, and typed follow-needed conjectures with explicit
  route targets for missing authority-title vs legal-ref coverage
- AU fact-review bundles now surface that same routing metadata directly in
  `operator_views.authority_follow`, so operator-facing review can see
  route-target counts and a bounded follow-needed queue without opening the
  raw semantic-context payload
- the intended next layering is now explicit in docs:
  cite-like hint -> persisted authority receipt -> lightweight authority
  substrate summary -> explicit deeper bounded follow only when a concrete
  unresolved conjecture remains
- that runtime split is now explicit in `docs/user_stories.md`:
  citation-driven authority follow/ingest is a real story the repo claims at
  the source-pack/HCA/operator seam level, while ordinary AU semantic runtime
  now uses an explicit documented receipt-consumption path; parser-seen
  cite-like text alone is still not enough to trigger live authority ingest

## Objective
Keep the new AU/Wikidata/GWB review artifacts documented in the same terms the
repo now implements, and make the next cross-lane normalization step explicit.

## Near-term intent
- Preserve additive review builders above the existing handoff/checkpoint
  artifacts; do not rewrite the old contracts.
- Treat review-geometry parity as achieved, but shared metric vocabulary as the
  next unresolved step.

## Recent decisions (2026-03-26)
- The repo now has review-geometry parity across AU, Wikidata, and GWB:
  - review items
  - source review rows
  - unresolved clusters
  - cues / anchors
  - ranked provisional rows
  - bundled review queues
- Wikidata now has:
  - checked structural review:
    `tests/fixtures/zelph/wikidata_structural_review_v1/`
  - dense structural review:
    `tests/fixtures/zelph/wikidata_dense_structural_review_v1/`
- GWB now has:
  - checked public review:
    `tests/fixtures/zelph/gwb_public_review_v1/`
  - broader review:
    `tests/fixtures/zelph/gwb_broader_review_v1/`
- Current lane readings are now explicit in
  `docs/planning/review_geometry_parity_20260326.md`.
- The next architectural step is not immediate shared-code extraction.
- The next architectural step is a normalized cross-lane summary block so AU,
  Wikidata, and GWB metrics become directly comparable rather than only
  shape-compatible.
- External Wikimedia grant/funding state was checked online on 2026-03-26:
  - there are active/open movement funding paths relevant to Wikidata work
  - there is not one simple official "all active Wikidata grants" list
  - repo docs should therefore separate external funding state from internal
    review-surface status
  - external grant framing should follow existing Wikimedia proposal patterns
    rather than pitching the repo as an abstract SL/ITIR system
  - the current bounded lane maps most naturally to:
    - a provenance-aware Wikidata validation and ingestion tool
    - Rapid Fund if scoped as a bounded tool/demo
    - Research Fund if scoped as a methodology/evaluation project
  - the next repo-facing artifact for this is
    `docs/planning/wikimedia_grant_framing_20260326.md`
  - a concrete repo-local Rapid Fund-ready draft plus ZKP formalization now
    exists in:
    `docs/planning/wikimedia_rapid_fund_draft_20260326.md`
  - that draft has now been tightened into Wikimedia-style application fields
    with explicit evaluation metrics, acceptance criteria, and risk/mitigation
    notes so the next step is submission translation, not first-pass proposal
    invention
  - the bounded demo/evaluation collapse is now explicit in:
    `docs/planning/wikimedia_bounded_demo_spec_20260326.md`
  - chosen demo shape now uses:
    - foreground repo-owned structural packs:
      - mixed-order
      - `P279` SCC
      - pinned qualifier drift
      - bounded disjointness
    - secondary attributed appendix examples:
      - `GNU` / `GNU Project`
      - finance entity-kind-collapse
  - chosen baseline is:
    - primary: manual bounded review
    - secondary: current repo checked-review process
  - chosen reviewer route is:
    - preferred: `1-2` Wikidata/ontology-adjacent reviewers
    - fallback: `1-2` technically adjacent reviewers
  - reviewer story should explicitly name:
    - mixed-order class/instance confusion
    - SCC/circular-subclass pressure
    - qualifier drift
    - structural contradiction review
    - secondary appendix only: entity-kind collapse
  - attribution discipline now needs to stay explicit in grant/demo docs:
    - `GNU` / `GNU Project` should not be framed as a repo-original discovery
    - broader `P2738` disjointness-method context should credit Ege Doğan and
      Peter Patel-Schneider
    - repo claims should stay on bounded fixture-backed implementation and
      review surfaces
  - attribution/case-lineage matrix for the Wikimedia demo lane now lives in:
    `docs/planning/wikimedia_demo_attribution_matrix_20260326.md`
  - the clearest explicit GNU-adjacent case to treat cautiously in the same
    Rosario-shaped hotspot/page-review wave is:
    `finance_entity_kind_collapse_pack_v0`
  - prior-work/originality rule surface for the Wikimedia lane now lives in:
    `docs/planning/wikimedia_prior_work_and_originality_note_20260326.md`
  - current safe originality claim is bounded:
    - prior work informs the benchmark/disjointness/hierarchy framing
    - repo contribution is the provenance-aware, fixture-backed review/reporting
      surface
    - do not claim reproduction, parity, or first discovery without stronger
      repo evidence

## Recent decisions (2026-03-27)
- Added a bounded climate-change property-migration protocol note:
  `docs/planning/wikidata_climate_change_property_migration_protocol_20260327.md`
- The anchor case is the live community question around
  `carbon footprint (P5991)` vs `annual greenhouse gas emissions (P14143)`.
- The repo posture for this class of problem is now explicit:
  - treat it as a bounded migration-review lane
  - do not treat it as a property-rename or whole-property bot rewrite
  - preserve statement-bundle shape:
    - value
    - rank
    - qualifiers
    - references
  - reuse revision-window and qualifier-drift methods before claiming a case is
    migration-safe
  - generate review surfaces first and any edit/export surface only from
    checked-safe subsets
- The external coordination context checked on 2026-03-27 was:
  `Wikipedia:WikiProject Climate change`
  (`https://en.wikipedia.org/wiki/Wikipedia:WikiProject_Climate_change`,
  source = web)
- The useful signals pulled from that page were:
  - recommended-source discipline is explicit
  - controversial-topic editing discipline is explicit
  - visible to-do and article-alert queues are explicit
  - article metrics/prioritization surfaces are explicit
- The repo should therefore frame climate-change migration help as:
  - provenance-aware review support
  - explainable migration buckets
  - checked sample first
  - no opaque one-shot mass-edit recommendation
- Added a sharper ZKP interpretation for the external coordination surface:
  - `Wikipedia:WikiProject Climate change` is best modeled as:
    - upstream noisy substrate
    - proposal/candidate-generation surface
    - public review/acceptance context
  - it is explicitly not:
    - the semantic truth layer
    - the admissibility lattice
    - the migration engine
- This is aligned with earlier repo doctrine for Wikipedia ingest:
  - revision-locked article -> canonical wiki state -> projections
  - compare normalized state first, then derive reviewer-facing deltas
- The current `Phi` prototype now emits structured explanation witnesses:
  - type witness
  - role witness
  - authority witness
  - constraint check
  - scope check
- `mapping_explanation` is now part of the executable contract, so the bridge
  from `Phi_meta` admissibility to `Phi_ij` outcome is machine-readable rather
  than only free-text rationale.
- Cross-system mapping now has a bounded meta gate:
  - schema:
    `schemas/sl.cross_system_phi_meta.v1.schema.yaml`
  - runtime:
    `src/cross_system_phi_meta.py`
  - current `Phi` prototype now emits:
    - `meta_validation` receipts on admitted mappings
    - `meta_validation_report.blocked_pairs` for inadmissible candidates
- The current behavior split is now explicit:
  - `Phi_meta` decides whether a candidate pair is admissible
  - `Phi_ij` only classifies admitted pairs as
    `exact|partial|incompatible|undefined`
- The bounded cross-system `Phi` package now has a real promoted-record
  prototype:
  - runtime:
    `src/cross_system_phi.py`
  - contract additions:
    `provenance_rule`, `provenance_index`, `mismatch_report.workflow`
  - validation:
    `tests/test_cross_system_phi_prototype.py`
- The prototype is intentionally narrow:
  - two systems only
  - built over existing promoted semantic-report rows
  - one explicit partial mapping path
  - one explicit incompatible path
  - dual-anchor provenance required for every mapping/diagnostic ref
- For the `P5991 -> P14143` lane, this means:
  - public consensus can authorize/prioritize
  - but migration safety still has to be established in a separate bounded
    statement-bundle review surface
- The climate-change migration note now also carries a formal cross-system
  mapping:
  - `Φ : W × Π × Κ → L(P)`
  - factorized as ingest -> extract -> normalize -> bundle -> classify ->
    promote -> graph
- The first executable migration artifact now exists:
  - contract note:
    `docs/planning/wikidata_migration_pack_contract_20260328.md`
  - schema:
    `schemas/sl.wikidata_migration_pack.v1.schema.yaml`
  - CLI:
    `sensiblaw wikidata build-migration-pack`
  - runtime:
    `src/ontology/wikidata.py`
- `L(P)` is now documented as a typed promoted-fact graph over:
  - article/revision/source/task nodes
  - claim/reference/qualifier bundles
  - migration/review cases
  - conflict/uncertainty/motif control nodes
- The note now makes several climate-specific constraints explicit:
  - provenance path required for promoted claims
  - controversial-topic guard for climate-sensitive claims
  - bundle integrity over main-snak-only comparisons
  - abstention admissibility
  - bounded-slice requirement before bulk migration
  - no bot export before checked-safe subset
  - revision-window consistency
- The immediate unresolved design fork is now explicit:
  - the `MigrationPack v0.1` path is now concrete in Python/JSON
  - the remaining fork is whether a later formal layer should also mirror this
    in Agda-style records/specs
- Current `MigrationPack v0.1` runtime buckets are:
  - `safe_equivalent`
  - `safe_with_reference_transfer`
  - `qualifier_drift`
  - `reference_drift`
  - `split_required`
  - `abstain`
- Candidate rows now also carry a narrow action field:
  - `migrate`
  - `migrate_with_refs`
  - `split`
  - `review`
  - `abstain`
- Split detection is now framed generically:
  - detect independent axes over the statement bundle and sibling slot context
  - emit those axes per candidate as `split_axes`
  - treat `split_required` as a failed 1:1 lossless mapping, not as a
    climate-only heuristic
- A first live bounded `P5991 -> P14143` pilot pack is now pinned in:
  - `SensibLaw/data/ontology/wikidata_migration_packs/p5991_p14143_climate_pilot_20260328/`
  - materialized by:
    `SensibLaw/scripts/materialize_wikidata_migration_pack.py`
  - selected QIDs:
    - `Q56404383`
    - `Q10651551`
    - `Q10416948`
    - `Q10403939`
    - `Q10422059`
  - observed bucket distribution:
    - `safe_with_reference_transfer`: 2
    - `ambiguous_semantics`: 55
  - rebuilding the pinned slice under the new split heuristics now yields:
    - `safe_with_reference_transfer`: 1
    - `split_required`: 56
- The first live pilot exposed and resolved one real classifier issue:
  - migration-pack review gating must be driven by evidence presence
    (`sum_e >= e0`), not by non-zero `tau`
  - otherwise normal-rank referenced statements collapse incorrectly to
    `abstain`
- The live materializer now supports both practical operator entry modes:
  - explicit QID input via repeatable `--qid`
  - bounded live discovery via `--discover-qids --candidate-limit N`
- Discovery mode returns the exact selected QIDs in the emitted manifest so the
  bounded sample remains auditable even when the operator starts without a
  prebuilt set
- The first OpenRefine bridge now exists as a flat CSV exporter over
  `MigrationPack` JSON:
  - CLI:
    `sensiblaw wikidata export-migration-pack-openrefine`
  - output shape includes bucket / drift / review columns for faceting
  - intended boundary:
    SensibLaw classifies, OpenRefine reviews, execution remains separate
- A first checked-safe export now also exists:
  - CLI:
    `sensiblaw wikidata export-migration-pack-checked-safe`
  - output shape is a flat CSV over only `safe_equivalent` and
    `safe_with_reference_transfer` rows
  - intended boundary:
    staging/export for already-safe rows only, still not a direct edit payload
- A first bounded migration verifier now also exists:
  - CLI:
    `sensiblaw wikidata verify-migration-pack`
  - verification scope:
    checked-safe subset only
  - current statuses:
    `verified`, `duplicate_target`, `target_present_but_drifted`,
    `target_missing`
  - intended boundary:
    prove target presence/preservation for safe rows before any broader
    execution claim
- A first split-row followthrough artifact now also exists:
  - note:
    `docs/planning/wikidata_split_plan_contract_20260328.md`
  - schema:
    `schemas/sl.wikidata_split_plan.v0_1.schema.yaml`
  - CLI:
    `sensiblaw wikidata build-split-plan`
  - scope:
    review-only plans for structurally decomposable `split_required` slots
  - intended boundary:
    propose `1 -> N` target bundles without yet emitting split edits
- A broader docs-first `ProposalArtifact v1` layer is now explicitly recorded:
  - note:
    `docs/planning/proposal_artifact_contract_v1_20260328.md`
  - `SplitPlan` and `EventCandidate` are now treated as the first two explicit
    mapped subtypes already present in the repo
  - the affidavit coverage/review lane is treated as the cross-domain
    stress-test/reference case
  - decision:
    do not refactor runtimes to a shared base type yet; the remaining question
    is shared-runtime value and fit, not absence of a second subtype
- The live materializer now has a one-step operator mode:
  - discover or accept QIDs
  - materialize the bounded pack
  - emit the OpenRefine CSV via `--openrefine-csv`
  - return both artifact paths in one summary JSON
- Current operator truth for Nat/full-set use:
  - the lane is already good enough to classify and filter a large/full set
  - it yields:
    - a `migration_pack.json`
    - an OpenRefine CSV
    - a candidate safe subset
  - it is not yet good enough to be presented as:
    - a final migration executor
    - a fully trusted import sheet
    - a complete machine decision for every statement
- Current plain-language boundary for operator explanation:
  - the lane is doing structured statement-bundle checks
  - it is not yet reading source text or performing deep logic/meaning
    analysis over prose
  - the safest explanation is:
    it helps separate "probably safe" from "please review this first"
- Immediate next product/implementation goal for this lane:
  - reduce the large temporal/multi-value `ambiguous_semantics` bucket
  - start with `split_required` and a clearer action model for reviewer-facing
    output
- Current next-step bridge decision:
  - if text-aware evidence is added to this lane, it should pass through the
    bounded bridge contract in:
    `docs/planning/wikidata_phi_text_bridge_contract_20260328.md`
  - `Phi` should compare:
    - structured migration-pack rows
    - promoted text observations
    - resulting pressure outputs
  - `Phi` should not become raw text -> migration decision
- First executable bridge scaffolding now exists:
  - schema:
    `schemas/sl.wikidata_phi_text_bridge_case.v1.schema.yaml`
  - runtime helpers in `src/ontology/wikidata.py`:
    - `build_wikidata_phi_text_bridge_case(...)`
    - `attach_wikidata_phi_text_bridge(...)`
    - `extract_phi_text_observations_from_observation_claim_payload(...)`
    - `attach_wikidata_phi_text_bridge_from_observation_claim(...)`
  - additive migration-pack fields now exist:
    - `bridge_cases`
    - `text_evidence_refs`
    - `bridge_case_ref`
    - `pressure`
    - `pressure_confidence`
    - `pressure_summary`
  - current limitation:
    the bridge is runtime-real and can consume the Observation/Claim contract
    as a real producer seam, but this migration lane still lacks a dedicated
    climate-text producer of its own
- The strongest literature-backed reading from the local papers is:
  - Rosario supports benchmark/test-surface construction from ontology
    fragments
  - Ege/Peter support query/report/culprit-finding and community-facing repair
    workflows
  - Zhao/Takeda support user-facing inspection and risk-oriented diagnosis for
    hierarchy inconsistency
  - together they support the repo's review-support boundary, not a claim of
    mature end-to-end migration automation
- Still deferred:
  - `needs_human_review`
  - `non_equivalent`
  - `safe_add_target_keep_source_temporarily`
  - `ambiguous_semantics` as a narrower residual bucket, if still needed after
    explicit split heuristics
  - checked-safe export
  - post-edit verification

## Completed prior milestones
- Sprint S5: actors, actions/objects, scopes, lifecycle, graph projection, stability hardening — shipped and flag-gated.
- Sprint S6: query API, explanation surfaces, projections, alignment, schema stubs, and guard review completed; no-reasoning contract enforced.
- Sprint S7: TextSpan contract + Layer 3 enforcement for rule atoms/elements.
- Sprint S8: non-judgmental cross-doc topology (`obligation.crossdoc.v2`).
- Sprint S9: read-only UI hardening (fixtures, Playwright smoke, obligations tab).

## Milestone scope
- Deliver read-only, deterministic surfaces over the existing normative lattice: queries, explanations, alignment, projections, schemas.
- Keep LT-REF, CR-ID/DIFF, OBL-ID/DIFF, and provenance invariants frozen; no compliance or interpretive behavior.

## Dependencies / infra constraints
- None new; spaCy/Graphviz/SQLite remain the baseline.

## Assumptions
- Python 3.11 target with 3.10 fallback; Ruff formatting.
- Clause-local, text-derived extraction; no cross-clause inference.

## Recent decisions (2026-03-08)
- Random Wikipedia page quality is now explicitly framed as an article-ingest
  lane first:
  - primary target is article-wide bounded structure over arbitrary revision-
    locked pages
  - the important question is which people/entities the article names, what
    they did, and which bounded text-local context can be retained cleanly
  - timeline readiness remains a derived quality surface, not the whole lane
  - one-hop follow is the initial expansion cap
  - legal-specific scoring remains a comparison slice, but arbitrary non-legal
    pages should still be pressure-tested through the article-ingest lane
- The Wikipedia ingest middle is now explicitly:
  `revision-locked article -> canonical wiki state -> projections`
  where the canonical wiki state should reuse sentence/text units,
  observation-style rows, conservative `EventCandidate`s, claims, attributions,
  and anchor-status metadata rather than treating anchored timeline rows as the
  ingest ontology.
- `timeline` remains the user-facing chronology surface, but it should include
  ordered undated events as well as anchored ones; anchor status must remain
  explicit so chronology quality is not overstated.
- The revision harness should compare canonical wiki state first and only then
  summarize graph/timeline/editorial deltas for reviewer support.
- The random-page article-ingest report should now expose two parallel score
  families:
  - legacy coverage scores for comparability with the earlier harness
  - honesty scores that explicitly penalize observation explosion, malformed
    extracted text, and weak actor/object binding
- Timeline chronology quality should remain visible but separate:
  - expose explicit/weak/none anchor ratios and a timeline-honesty score
  - do not let mostly undated pages automatically drag down the main
    article-ingest honesty score
- Density metrics such as observations per sentence, observations per event,
  and step density should be treated as first-class operator signals rather
  than hidden debug numbers.
- The random-page report should now also expose a third scorer-only
  calibration layer:
  - abstention quality on list-like/taxonomic/measurement-heavy sentences
  - sentence-link relevance against extracted actor/object structure
  - claim/attribution grounding quality
- Page-family stratification should now be explicit and bounded:
  - heuristic families such as `biography`, `place`, `facility`,
    `project_institution`, `species_taxonomy`, and `general`
  - used for operator interpretation and summary rollups, not as a learned
    classifier target
- Current stored-manifest findings after the calibration pass:
  - abstention calibration is informative on `Agrega` and
    `Euchlaena deductaria`
  - weak object binding still fires broadly and should not yet be read as a
    settled extractor failure without stronger family-aware interpretation
  - current link-relevance scoring saturates near `1.0` on the stored random
    manifest and still needs a stronger centrality/follow-yield formulation
    before it is trusted as a discriminating metric
- Referenced but unresolved online ChatGPT thread:
  - online UUID: `69c0b4d1-d714-839b-b21c-ce162292db4f`
  - source used: prior local context plus failed later refresh attempt
  - live fetch blocker: unresolved `re_gpt` refresh-path failure; likely in the
    request/auth flow rather than safe to assume a stale token
  - correction:
    - this later refresh failure does not imply the original pull never
      succeeded
    - the more accurate reading is that earlier ingestion/context use may have
      worked, while this pass simply failed to re-verify the thread live
- A newer graph-quality follow-up thread is now explicitly tracked:
  - online UUID: `69c0bd1d-389c-8399-a23e-10efab70a1a9`
  - suspected topic: graph-quality improvement / `PositiveBorelMeasure`
    followthrough
  - current blocker: `re_gpt` auth bootstrap reproduced a warning-banner-only
    `/api/auth/session` response, which points to missing frontend-cookie
    hydration rather than a safe “stale token” diagnosis
  - current post-fix status:
    - the auth bootstrap path is now patched and tested for warning-banner
      fallback behavior
  - the target thread is still not recovered because the current
    session-token-only frontend path renders `client-bootstrap` as logged out
  - required next step: recover that thread after the auth-bootstrap fix and
    then re-evaluate the graph centrality / follow-yield lane with its sharper
    wording
- Wikipedia ingest regime basis:
  - the canonical wiki article state now carries a small regime vector
    (`narrative`, `descriptive`, `formal`)
  - the random-page article-ingest report emits regime-aware honesty and
    calibration scores alongside the legacy compatibility fields
  - the stored random-page manifest now shows a sensible split:
    biography/facility/project/species pages stay descriptive-heavy while the
    math/formal path can be stressed separately
  - the next phase is a generalization harness with dominant-regime counts and
    follow-yield summaries so graph usefulness can be tested on larger random
    slices
  - follow-yield now uses the explicit richness / non-list / regime /
    information-gain blend for follow-target quality, then adds hop decay and
    best-path probing so continuation quality can be falsified directly
  - first live recursive campaign result:
    - root-link relevance stayed high (`0.982143`) while followed-link
      relevance fell to `0.5625`
    - follow-target quality averaged `0.446047`
    - hop-2 quality did not collapse versus hop-1 on the first 8-page slice
    - best-path remained above average candidate path quality by `0.055025`
  - immediate empirical bottleneck:
    - weak follows clustered around `non_list_score = 0.0`
    - list/year/generic aggregation pages are the next target, not regime
      redesign or deeper path analytics
  - implemented followthrough:
    - archived multi-run campaign execution now lives in
      `scripts/run_follow_quality_campaign.sh`
    - aggregated report clustering now lives in
      `SensibLaw/scripts/analyze_follow_quality_reports.py`
    - `non_list_score` now incorporates title-level and warning-level
      aggregation cues so list/year/disambiguation-like follows are penalized
      before deeper graph metrics are revisited
  - bug fix after the first 3-run aggregate:
    - raw `[[Category:...]]` residue in stored wikitext was falsely driving
      some ordinary pages into `list_like_follow`
    - category/defaultsort markup is now stripped before non-list marker
      evaluation
  - corrected aggregate after that fix:
    - 24 root pages / 3 runs still left `list_like_follow` as the primary
      weak-follow bucket
    - `low_information_gain_follow` remained the next residual bucket
    - root-link relevance stayed high, hop decay stayed near zero, and the
      graph still looked walkable rather than collapsing with depth
  - slice-1 continuation-specificity implementation:
    - the follow-target-quality blend and current thresholds stayed fixed
    - `non_list_score` / `list_like_follow` now absorbs bounded title
      heuristics, lexical parent-child specificity checks, and same-
      neighborhood/no-lift detection
    - follow details and summaries now emit explicit specificity reasons
    - the next validation step is the same 3x8 campaign rerun before changing
      `low_information_gain_follow`
  - post-slice-1 rerun reading:
    - the live rerun confirms the new specificity reasons are hitting the
      intended weak continuation shapes
    - but because the sample changed, the next quantitative step should be a
      fixed-manifest before/after comparison
    - the next scorer refinement after that should stay inside the existing
      information-gain component and target related-but-generic continuations
  - fixed-manifest + slice-2 implementation:
    - `scripts/run_follow_quality_campaign.sh` can now rescore stored manifests
      by reusing an existing run root
    - `SensibLaw/scripts/compare_follow_quality_reports.py` compares before/after
      reports on the same manifests
    - the information-gain component now carries bounded penalties for
      year/umbrella/generalization and low-novelty continuations while keeping
      the overall score shape unchanged
    - fixed-manifest comparison then showed:
      - `list_like_follow` unchanged on the same manifests
      - `low_information_gain_follow` only slightly higher
      - average `follow_target_quality_score` lower (`0.525836 -> 0.507564`)
      - `best_path_vs_avg_gap` slightly higher (`0.047057 -> 0.050072`)
      - `hop_quality_decay` effectively flat (`-0.021348 -> -0.019689`)
    - current reading:
      - fixed-manifest compare path is correct and should stay
      - information-gain reason instrumentation is useful and should stay
      - title-shape cues alone are too blunt as score penalties
      - the next scorer narrowing should require co-occurring low-novelty /
        no-lift evidence before the main year/umbrella/generalization
        information-gain penalties apply
    - narrower `v0_9` rescoring then showed:
      - weak-follow bucket counts unchanged on the same manifests
      - average follow-target quality nearly flat rather than materially lower
      - hop decay and best-path gap effectively stable
      - information-gain reasons remained visible even when they did not
        trigger score penalties
    - next scorer step:
      - stop tightening title cues
      - add a content-based continuation-lift signal inside the existing
        information-gain component so relation-bearing structural lift can
        distinguish genuinely informative continuations from generic title
        matches
- A separate auth/input format issue is also now in play:
  - local file `~/.chatgpt_session_new` is a chunked session-token file with
    multiple raw lines
  - `re_gpt` should learn that format explicitly rather than treating it like a
    single-line token file

- 2026-03-24 online Context resolution attempt (SensibLaw thread refresh):
  - online UUID: `69c27a0a-ed74-839c-8a57-3c184c28f88e`
  - title from input URL:
    `https://chatgpt.com/g/g-p-6983ff87bc608191905a33b93daa74f7-sensiblaw/c/69c27a0a-ed74-839c-8a57-3c184c28f88e`
  - decision:
    - **source:** `error` (resolver: local DB miss + web fallback failure)
    - **decision reason:** `not_found_in_db`; web fallback could not complete
    - canonical thread ID: unresolved
    - main topics: context refresh verification request only; no canonical match
      extracted
  - failure details:
    - `re_gpt` hit Playwright browser bootstrap and required `firefox` at
      `/home/c/.cache/ms-playwright/firefox-1509/firefox/firefox`
    - install path currently unavailable in this environment, so cloudflare
      auth path could not be solved
  - next action:
    - use `pull_to_structurer.py` to ingest from online ID first and re-resolve from DB
      in the same session
- 2026-03-24 context resolution correction for the same SensibLaw thread:
  - online UUID: `69c27a0a-ed74-839c-8a57-3c184c28f88e`
  - title: `QG Unification Proofs`
  - canonical thread ID: `f20d9304aae805879a1f934b71443bd2c80ac19b`
  - source used: `db` (post pull-to-structurer ingestion)
  - decision reason: `db_match_found` via `online_thread_id_exact`
  - pulled with:
    - `/home/c/Documents/code/ITIR-suite/.venv/bin/python
      /home/c/Documents/code/ITIR-suite/reverse-engineered-chatgpt/scripts/pull_to_structurer.py --ids "69c27a0a-ed74-839c-8a57-3c184c28f88e" --db ~/chat_archive.sqlite --engine async --json`
  - resolved content summary:
    - `thread_message_count`: 42
    - earliest_ts: `2026-03-24T11:48:25+00:00`
    - latest_ts: `2026-03-24T11:54:22+00:00`
  - no firefox/browser path is required for this online-ID workflow when using direct pull
  - next action:
    - if a future direct pull attempt fails, log the concrete blocker and retry only with
      corrected authentication/session inputs before trying browser-based resolver fallback
- Wikidata ontology lane now uses the newest pinned slice/revision as the active
  baseline for routine diagnostics; explicit historical rewind checks are now
  tracked as a separate review-triggered process because they are useful but add
  non-trivial context overhead.
- The pinned qualifier-drift review pack remains `Q100104196|P166` plus
  `Q100152461|P54` for reproducibility; a fresh 2026-03-08 live rerun also
  confirmed `Q1000498|P166` as a new medium candidate, but that case is not yet
  promoted into the pinned review pack.
- Wikipedia revision monitoring now has two deliberately different curated
  packs:
  - `wiki_revision_monitor_v1` for mixed baseline + ontology-stress pages
  - `wiki_revision_contested_v1` for live high-contestation pages across
    politics, ongoing conflict, religion, and politicized science/medicine
- The next revision-monitor step is now fixed as a bounded history-aware
  runner:
  - keep current-vs-last-seen state
  - poll bounded recent revision windows
  - score candidate deltas before full extraction
  - materialize only the top selected pairs
  - add section-aware targeting to pair reports and issue packets
- Cross-project interface posture for that lane is fixed:
  - `SensibLaw` owns source comparison and pair-report production
  - `SL-reasoner` may consume pair reports read-only
  - `StatiBaker` may ingest observer-class refs only
  - `fuzzymodo` and `casey-git-clone` remain reference-only external consumers
    at this stage
- Current doctrine for the wiki revision pack runner:
  - do not prioritize GUI/workbench integration yet
  - do prioritize bringing the lane up to the same functional standard as the
    stronger suite pipelines
  - the important convergence points are deterministic producer-owned outputs,
    queryable run/result state, additive read models, and shared review/
    provenance posture so other pipelines can propagate/reuse the lane cleanly
- The current contested-page extension is now fixed:
  - `wiki_revision_contested_v2` is the deeper curated contested pack with
    graphing enabled
  - contested-region graphs are hybrid review artifacts built from selected
    revision pairs, section deltas, extraction deltas, and epistemic deltas
  - detected cycles mean bounded revisitation of the same contested region,
    not contradiction proof or truth adjudication
  - the first UI consumer is a dedicated `itir-svelte` page
    (`/graphs/wiki-revision-contested`), backed by the dedicated revision
    monitor SQLite store plus graph artifacts
- Current doctrine for OpenRecall integration:
  - treat the vendored `openrecall/` project as an upstream local-first
    observer/capture source
  - import into ITIR/SensibLaw via normalized append-only capture tables/read
    models rather than treating OpenRecall as a semantic authority
  - reuse imported captures in existing lanes first (mission-lens actual side,
    source-local text units for semantic/transcript extraction)
  - do not prioritize GUI-first integration or direct SB writing before the
    functional/import/query standard is in place
  - first bounded implementation slice now exists:
    - `scripts/import_openrecall.py`
    - normalized `itir.sqlite` capture tables/read models
    - mission-lens `openrecall_capture` actual rows
    - `load_openrecall_units(...)` for source-local semantic reuse
  - next functional slice is query/read-model parity:
    - now implemented through:
      - `src.reporting.openrecall_import`
        - `load_openrecall_import_runs(...)`
        - `build_openrecall_capture_summary(...)`
        - `query_openrecall_captures(...)`
      - `scripts/query_openrecall_import.py`
    - provides:
      - latest import-run summaries
      - capture counts by app/title/date
      - screenshot coverage summaries
      - recent capture-row queries through a neutral helper + CLI seam
- Archive/context source for the contested-pack expansion:
  - title: `Highly Contested Wiki Pages`
  - online UUID: `69ada623-351c-839a-97c4-7669a12b8e04`
  - canonical thread id: unresolved locally because `~/chat_archive.sqlite`
    was locked during persistence
  - source used: `web`
  - main decision pulled: broaden revision-monitor testing with a second
    curated volatility pack rather than folding all new pages into the
    ontology-stress set
- Broad GWB surfaces such as `Congress`, `Iraq`, `veto`, and `Supreme Court`
  remain acceptable extraction targets; the tightening task is specifically
  about promotion into reviewed U.S.-law linkage lanes, which should require
  stronger co-signals.
- The next semantic pressure-test after the AU legal fixture lane should be
  bounded freeform/transcript text, using the same frozen
  `entity -> mention_resolution -> event_role -> relation_candidate ->
  semantic_relation` spine with strong abstention on ambiguous speaker/actor
  cases.
- GWB linkage broad-cue tightening is now implemented in bounded form:
  broad-cue-only cases can remain visible as low-confidence matched/candidate
  output when unambiguous, but they no longer escalate medium/high confidence
  without stronger non-broad receipts.
- A bounded transcript semantic v1 lane now exists over `TextUnit` +
  deterministic speaker inference, persisting source-local speaker mention
  resolution and `speaker` event roles in the shared semantic tables while
  keeping conversational `replied_to` output candidate-only.
- That transcript/freeform lane is now the first profile-neutral SL semantic
  baseline for human text: broad source-local entities are allowed in
  freeform/journal text, explicit affect/state cues can emit candidate-only
  `felt_state` relations, and legal predicates remain gated to explicit
  AU/GWB/legal entrypoints rather than loading by default.
- The generalized freeform entity heuristics are now tightened in bounded
  form: contextual single-token person/place surfaces remain allowed, but
  obvious titlecase noise such as `Thanks`, `Today`, and role/system labels is
  suppressed instead of becoming source-local actors.
- The transcript/freeform lane now also has a first bounded explicit
  social-relation slice for named statements such as sibling/parent/spouse/
  friend assertions plus explicit guardian/care surfaces. These remain
  candidate-only and text-local by default; there is still no open-world,
  institutional-custody, or first-person social inference pass.
- Care relation naming in that lane should now stay relation-style and
  tense-neutral: canonical predicate `caregiver_of`, observed text kept in
  receipts (`cared_for`, `cares_for`, similar) rather than in predicate keys.
- The transcript/freeform lane now also needs a compact relation-review
  summary artifact so promotion decisions are based on bounded counts/cues
  instead of full JSON report inspection alone.
- The semantic workbench ownership boundary is now tighter: Python report
  producers should emit `text_debug` directly, and `itir-svelte` should render
  that artifact instead of re-deriving token anchors, relation families, or
  opacity locally.
- Semantic review reports should now also expose a compact `review_summary`
  read model across GWB/AU/transcript so predicate totals, cue surfaces, and
  excluded `text_debug` rows are comparable in one place.
- The `text_debug` contract should now carry producer-owned char spans plus a
  source artifact id per anchor. Token spans remain view helpers; they are no
  longer the only shared anchor surface.
- The token-arc workbench should now also lightly echo same-role anchors in the
  same relation family when a token/anchor is active, using the active family
  color with opacity scaled by relation strength.
- The semantic report workbench should now use producer-owned `text_debug`
  spans for event-local viewer cross-highlighting. If a corpus cannot provide a
  real source document, the source-document panel should stay explicitly
  unavailable rather than substituting event text.
- Transcript/freeform reports now emit grouped source-document text plus
  source-level event spans, allowing the semantic workbench source viewer to
  project event-local anchor highlights into real source text without moving
  semantic derivation back into TS.
- GWB/AU semantic reports now also emit grouped timeline-source text plus
  source-level event spans from the normalized wiki timeline store, so the
  semantic workbench source viewer is no longer transcript-only and still does
  not need TS-side source reconstruction.
- Local archive/context review shows the prior stable vocabulary is around the
  actor identity spine and shared role/slot boundaries (`subject`, `object`,
  `requester`, `speaker`, `event_role`), not a settled transcript-specific
  role taxonomy. The transcript/freeform lane should align to those existing
  contracts instead of inventing new role labels ad hoc.
- Archive sweep anchors for actor/semantic-role recovery:
  - `21f55daa80206517e38f8c0fa56ee9bb2db8a9a0` (`Actor table design`):
    strongest archived actor-identity spine thread; relevant for actor table
    boundaries, identity modeling, and early `event_role` framing.
  - `691d79376cb653e7170ea6c200a0a1d0a34bec6b` (`Actor Model Feedback`):
    strongest archived semantic-spine thread for
    `mention_resolution -> event_role -> relation_candidate ->
    semantic_relation`.
  - `1802fc3d13a0ad01ad95cef07eeaae9c16c22bed`
    (`Milestone Slice Feedback`): relevant later thread for frozen-shape
    pressure testing, `subject`/`object` framing, and semantic diff posture.
  - `74f6d0e08de82556df95c6ab1edb51557fede4fa`
    (`Taxonomising legal wrongs`): high-signal ontology/taxonomy thread with
    many `subject`/`object` hits and broader SL legal-role context.
  - `4d535d3f33f54b1040ab38ec67f8f550a0f69dce` (`SENSIBLAW`): broad planning
    thread with recurring `subject`, `speaker`, and occasional `event_role`
    references across the larger SL/TiRCorder architecture.
  - `f8170d36e0b2c28b2bb0366a7dc35a433e26ca00`
    (`Feature timeline visualization`): secondary thread with repeated
    `speaker` and `event_role` mentions relevant to timeline/stream surfaces.
  - high-hit untitled archive threads `dbcfb20d67213216c7aa02ed8493ae21fd39730d`
    and `dff2e608e358fe5ed5cf1d0376a36ff8a87a6f2d` also mention `SensibLaw`
    heavily and should be mined later; titles/topics were not recoverable from
    the current bounded DB sweep.
- The first archive-ingestion pass is now written up in
  `docs/planning/archive_actor_semantic_threads_20260308.md`. Current
  extracted conclusions:
  - actor identity must stay small and clean
  - mention resolution is its own first-class layer
  - `event_role` evidence must remain separate from promoted semantic
    relations
  - transcript/freeform planning should reuse the shared role/slot language
    already present in the repo rather than inventing a transcript-only role
    taxonomy
- A second archive pass now isolates DB/table guidance in
  `docs/planning/actor_semantic_db_design_from_archive_20260308.md`.
  Main outcome:
  - current semantic v1.1 schema already matches the strongest later archive
    guidance around a unified entity spine, first-class mention resolution, and
    `event_role -> relation_candidate -> semantic_relation`
  - the remaining divergences are mostly narrower-or-deferred features from the
    older broader actor model: alias registry, merge audit, governed event-role
    vocabulary, and actor detail/annotation extension tables
  - the two untitled high-hit archive threads were mined enough to classify
    them as operational/noise for this topic, not missing actor DB design
- The first archive-backed identity-governance wave is now implemented in a
  shared actor layer rather than the `semantic_*` family:
  - shared `actors`, `actor_aliases`, `actor_merges`, and `event_role_vocab`
    now exist
  - actor-like semantic entities attach via
    `semantic_entities.shared_actor_id`
  - GWB/AU/transcript actor seeds now persist canonical/shared aliases into
    `actor_aliases`
  - the semantic spine itself remains unchanged:
    `entity -> mention_resolution -> event_role ->
    relation_candidate -> semantic_relation`
  - main post-implementation conclusion: the archive-backed “clean” schema was
    not really arguing for a different semantic core; it was arguing for shared
    identity governance around the existing core
  - next decision pressure is how far reviewed shared aliases should influence
    deterministic matching; current recommendation is conservative use first
    (registry/audit + seed-backed reuse) rather than broad alias-driven
    cross-lane matching
- The next bounded semantic-schema refinement should add DB-backed rule/slot/
  promotion metadata around the frozen v1.1 spine without replacing the
  current extractor code in one pass. Event anchoring remains mandatory:
  `event_role` stays the participation/context lane, and promoted
  `semantic_relation` rows must continue to point at the triggering event
  rather than becoming sentence-global facts.
- That rule/promotion refinement is now written up in
  `docs/planning/semantic_rule_slots_and_promotion_gates_20260308.md`.
  Chosen scope:
  - add first-class metadata for semantic rule types, slot definitions,
    selector-driven rule slots, and predicate-level promotion policies
  - seed it for the current GWB/AU/transcript predicate families
  - promotion should read shared predicate policy rows
  - emitted candidates/promoted relations should carry explicit rule-family
    receipts
  - confidence derivation should now start consulting shared policy minima and
    evidence requirements, while remaining profile-local for this phase
  - keep full extractor migration to a generic slot interpreter deferred
- The transcript/freeform semantic lane is now also exposed through a dedicated
  `SensibLaw/scripts/transcript_semantic.py` report entrypoint so
  `itir-svelte` workbench/debug surfaces can consume a real non-legal semantic
  producer without coupling directly to transcript helper internals.

## Recent decisions (2026-03-09)
- A first bounded Wikipedia revision harness now belongs in the repo as a
  read-only reporting lane over live article revisions. The chosen v0.1 shape
  is:
  - compare previous vs current revision metadata explicitly
  - measure both source-text and extraction-surface similarity
  - summarize local graph-facing impact
  - surface claim-bearing / attribution deltas
  - emit reviewer-facing issue packets plus a compact triage dashboard
- This harness is intentionally not an edit bot, not a Wikidata ontology
  mutation path, and not a truth adjudicator. Live volatility is treated as a
  reportable signal; authority boundaries remain unchanged.
- The next slice is a pack-level rolling runner, not a UI-first expansion:
  - selected article titles live in a pack manifest
  - last-seen state lives in a dedicated SQLite file, not `itir.sqlite`
  - current-vs-last-seen comparison is store-first rather than
    history-fetch-first
  - curated review context from the article pack is primary
  - bridge/alias auto-join is allowed as bounded secondary context only
  - the first consumer remains CLI-first, but outputs should be UI-ready
- The next public transcript/narrative proving case should use
  FriendlyJordies as a named public-media fixture for URL/transcript narrative
  validation. The target story is not "trust this source"; it is "ingest the
  source, extract narrative/proposition structure, and show what is supported,
  contradicted, selectively framed, or unresolved."
- A second linked user story should be treated as first-class planning scope:
  compare two competing narratives without collapsing them into one story.
  SensibLaw should eventually show common facts/propositions, disagreement,
  predicate/flow differences, and explicit receipts for both sides.
- Privacy rule for repo-facing docs: public-figure/public-media examples may be
  named, but private/family-style archive-derived examples should stay
  generalized or local-only even when they inform local planning.
- Packaging/user-story rule layered on top of that privacy rule: personal and
  private users should be treated as first-class consumers of partial stack
  layers (capture, timeline/reconstruction, bounded reference, safe export,
  provenance, local-first storage), but repo-facing docs should describe those
  users in generalized terms and should not collapse private use into
  institutional-style compliance/reporting language.
- Relevant local/web archive anchors for this decision:
  - `Climate Change Politics AU`
    (`69ac40e0-0cfc-839b-b2a8-0de3019379a9`, source used: `web`):
    public-media framing/corroboration design pressure; FriendlyJordies is the
    named public test case.
  - `Uncle's Conviction Inquiry`
    (`6949fb78-4688-8320-9ca9-03a65efaf711`, source used: `web`):
    disputed-record narrative design pressure; keep repo examples generalized.
  - `Bondi shooter neo-Nazi link`
    (`6940997c-0784-8324-94ae-2de2f0c34947`, source used: `web`):
    correction loops, attribution, and proposition-layer comparison matter
    more than rhetorical summarization.
- Archive tooling note: broad FTS-style mining over `/home/c/chat_archive.sqlite`
  is currently degraded because cross-thread analysis reports
  `sqlite3.DatabaseError: database disk image is malformed`. Exact/local
  lookups and direct web-thread inspection were still sufficient for this
  planning pass.

## Recent decisions (2026-03-07)
- Deterministic bridge seeding now refreshes the seeded slice when
  `source_sha256` changes, preventing stale local alias catalogs from masking
  newly reviewed bridge entries.
- Reviewed district-court alias variants are now part of the pinned bridge
  seed (`U.S./US/United States district courts`, `federal district courts`,
  `federal trial court`).
- GWB semantic deterministic promotion now includes review/litigation predicates
  (`ruled_by`, `challenged_in`, `subject_of_review_by`) while keeping cue-only
  rows candidate-gated.
- AU semantic legal-representative extraction now covers expanded
  `counsel/appeared-for` surfaces plus dotted suffix handling for
  `S.C./K.C./Q.C.` actor mentions.
- AU legal-representation cues are now externalized into a versioned lexical
  resource; cue matches bind clause-locally onto named representative mentions
  and abstain when no named representative signal exists, rather than creating
  synthetic actor rows from role labels.
- Added bounded docs for:
  - extraction vs enrichment boundary
  - mereology/parthood typed diagnostics
  - property/constraint pressure tests (including subset-vs-total and label
    harmonization as diagnostic-only signals)

## Recent decisions (2026-02-06)
- Canonical TextSpan model added (`revision_id`, `start_char`, `end_char`) and persisted on rule atoms/elements.
- Promotion receipts now carry span IDs; signals block promotion on overlap.
- Cross-doc topology upgraded to `obligation.crossdoc.v2` with `repeals/modifies/references/cites`.
- Read-only UI hardened: obligations tab, fixture payloads, and forbidden-language guard.
- Multi-modal doctrine + human tools integration captured for ITIR/SensibLaw.
- docTR profiling notes captured for SensibLaw root PDFs (pdfminer: 515 pages, 1,623,269 chars) with a follow-up timing run scheduled for 2026-02-06.

## Recent decisions (2026-02-11)
- HCA demo ingest (`case-s942025`) now prefers scored document links per row label; summary rows resolve to summary PDFs, not judgment HTML when both exist.
- Recording ingest no longer relies on a single Vimeo endpoint:
  - primary: `/video/<id>/config`
  - fallback: `/video/<id>/config/request` discovered from player HTML.
- Demo media export now includes transcript fallback from AV page transcript links plus HLS/DASH manifest artifacts when progressive MP4 URLs are absent.
- HCA AAO payload is now dual-lane:
  - `artifact_status` / `recording_artifact` rows from table/media adapter state.
  - `narrative_sentence` rows from sentence-local AAO extraction over ingested PDF text.
- HCA demo now emits `sb_signals.json` as observer-ready signals; contract is explicitly non-authoritative and reversible (truth/view separation preserved).
- HCA narrative sentence filtering moved to parser-first deterministic checks (spaCy token/POS), with regex retained only for fallback sentence splitting/hygiene.
- HCA narrative lane now emits structured `citations[]` and Wikipedia-first follower hints; citation tokens are no longer left as generic AAO objects.
- HCA narrative lane now also emits parser-native `sl_references[]` from source `document_json` reference lanes (`provisions`, `rule_tokens`, `rule_atoms`) with source provenance on each row.
- SB observer payloads now carry both `citations[]` and `sl_references[]` lanes, with `wiki_connector` follow hints (`wiki_pull_api.py`, preferred `pywikibot`) included in follower metadata.

## Recent decisions (2026-02-13)
- Wiki AAO context rendering in `itir-svelte` now preserves event anchor precision in
  context rows (`YYYY-MM-DD` when day anchor exists) instead of downcasting to the
  current timeline bucket granularity.
- Numeric key normalization now preserves explicit currency markers/symbols in canonical
  keys (e.g., `$5.6trillion` -> `5.6e12|usd`; `$500,000` -> `500000|usd`) while
  keeping parser-first numeric span detection with regex fallback only.
- Context sync revalidated via robust fetch for online thread
  `698e95ec-1154-83a0-b40c-d3a432f97239` (DB-first miss, live fetch success).
- Added thread-derived requirements register:
  `docs/wiki_timeline_requirements_698e95ec_20260213.md` to track implementation
  coverage and pending gaps from that context thread.
- Expanded that requirements register to include later-thread architecture
  requirements (`R15..R27`), covering identity/non-coercion, claim-bearing
  classification, quantified conflict logic, anchor graduation, typed edge basis
  metadata, numeric role typing, and explicit non-goals.
- Added sourcing/attribution layer artifacts from the same thread:
  - `docs/sourcing_attribution_ontology_20260213.md`,
  - `R28..R29` in `docs/wiki_timeline_requirements_698e95ec_20260213.md`,
  - model/test scaffold at `src/models/attribution_claims.py` and
  `tests/test_attribution_claims.py`.
- Added explicit architecture review closure matrix (10-point mapping) to
  `docs/wiki_timeline_requirements_698e95ec_20260213.md` to keep requirement
  IDs and statuses aligned with review feedback.
- Added canonical requirements register v2:
  `docs/wiki_timeline_requirements_v2_20260213.md` and switched active
  implementation tracking to v2 IDs/status fields (thread-trace register kept
  as provenance/history).
- Added baseline numeric role typing/alignment in wiki AAO extraction:
  step-scoped `numeric_claims` now attach canonical numeric values to governing
  verb steps with deterministic role labels (including `transaction_price` and
  `personal_investment` for multi-verb money sentences).
- Added claim-bearing extraction baseline in wiki AAO:
  step/event outputs now include profile-driven epistemic tags
  (`claim_bearing`, `claim_modality`, `claim_id`, `claim_step_indices`).
- Replaced extractor-hardcoded epistemic verb defaults with a dedicated
  deterministic classifier component (`src/nlp/epistemic_classifier.py`) and
  integrated dependency-first predicate typing into claim-bearing annotation,
  with profile lexical fallback retained for sparse parse cases.
- Added attribution/sourcing emission baseline in wiki AAO:
  event-level `attributions` (direct/reported for claim-bearing steps) plus
  top-level `source_entity` and `extraction_record` provenance objects.
- Added numeric claim context enrichment:
  claim payloads now emit structured normalized parts
  (`normalized.value/unit/scale/currency/magnitude_id`) and explicit temporal
  attribution (`time_anchor` and `time_years`) for timeline/date traceability.
- Added requester extraction hardening:
  possessive/title requester surfaces are canonicalized and alias-resolved
  (`President Obama's` -> `Barack Obama`) with deterministic fallback from
  `request` step subjects if possessor extraction is missing.
- Added requester coverage diagnostics:
  extractor now emits top-level `requester_coverage` counters and missing-event IDs
  for request-clause signals that did not resolve a requester actor.
- Added parser-agnostic ontology mapping baseline:
  `src/nlp/ontology_mapping.py` now canonicalizes action morphology fields
  (`tense/aspect/verb_form/voice/mood/modality`) with deterministic `unknown`
  fallbacks; extractor `action_meta` is wired through this mapping.
- Numeric currency+scale normalization no longer emits composite unit tags such as
  `trillion_usd`; keys are emitted as scientific value + currency
  (e.g., `$5.6trillion` -> `5.6e12|usd`).
- Numeric claims now preserve ontology-layer separation explicitly:
  `normalized` includes canonical magnitude identity plus
  `expression` (mantissa/scale/exponent/sig-fig/coercion) and
  `surface` (symbol/spacing/separator/hash) metadata.
- Subject/actor normalization now strips leading definite articles in extraction
  output (`the United States` -> `United States`) so subject-node identity does
  not fragment across article/no-article variants.
- Context sync revalidated for online thread
  `698eba02-3da4-839c-98c7-c9bcf062fa86`; Layer 3 `LegalSystem` is now treated
  as a normative authority boundary (sovereignty tier + parent hierarchy), not
  a country label.
- Authority-boundary schema migration added for legal systems (SQLite +
  Postgres tracks): `sovereignty_type`, `parent_system_id`,
  `commencement_date`, `constitutional_source_id`,
  `recognises_common_law`, `recognises_equity`, with AU sub-sovereign seed rows
  (`AU.STATE.*`) parented to `AU.COMMON`.
- Numeric claim extraction now enriches dependency-bound count units and targets
  (e.g., `71 lines of stem cells` -> `71|line` with `applies_to=stem cells`)
  and emits nearest sentence date text (`time_text`) alongside `time_anchor`.
- AAO action selection now has a parser-first classifier path
  (`src/nlp/event_classifier.py`) that maps spaCy `VERB|AUX` lemma/dependency
  signals to canonical action labels; regex action patterns are fallback-only
  and emit explicit `fallback_action_regex` warnings.
- Script execution bootstrap now inserts the SensibLaw root into `sys.path` for
  repo-root CLI invocations, so `src.nlp.event_classifier`,
  `src.nlp.epistemic_classifier`, and ontology mapping modules load reliably in
  normal extractor runs.
- Semantic backbone clarification captured:
  - WordNet/BabelNet are deterministic lexical-semantic resources (not LLMs),
  - canonical extraction path must remain non-generative,
  - any WSD in authoritative mapping must be deterministic and version-pinned.
- AAO extractor profile now enforces semantic-backbone determinism at runtime:
  non-deterministic profile settings (`llm_enabled=true` or unsupported
  `wsd_policy`) fail fast, and normalized semantic-backbone metadata is emitted
  in `extraction_profile`.

## Recent decisions (2026-03-06)
- Added a deterministic Wikidata statement-bundle projection operator spec with
  a ternary epistemic carrier, paraconsistent aggregation, and an Epistemic
  Instability Index (EII) metric to target volatile slots/class-order hotspots
  without prescribing fixes (`docs/wikidata_epistemic_projection_operator_spec_v0_1.md`).
- Archived and reviewed the \"Wikidata Ontology Issues\" thread for ontology
  diagnostics; added a doc mapping issue clusters to deterministic checks
  (`docs/wikidata_ontology_issue_review_20260306.md`).
- Added `deterministic_legal_v1` lexer candidate behind
  `ITIR_LEXEME_TOKENIZER_MODE=deterministic_legal` in `SensibLaw/src/text`,
  implemented without regex and with explicit section/subsection/paragraph
  structural spans.

## Chat context sync (2026-02-07)
- Source conversation: `ADR language vs SensibLaw`
  (`6986d38e-4b5c-839b-813a-608aa0de88d5`),
  latest assistant reply synced at `2026-02-07T06:01:41.279462Z`.
- Core extract:
  - SensibLaw should be framed as a domain profile over a domain-neutral
    lexical compression engine.
  - Reuse model: engine mechanics stay stable; SL/SB/infra profiles constrain
    admissibility only.
  - Guardrail: profiles may restrict accepted axes/groups but must not alter
    compression behavior.

## Chat context revalidation (2026-02-08)
- Revalidated live for `6986d38e-4b5c-839b-813a-608aa0de88d5`:
  title `ADR language vs SensibLaw`, last author `assistant`, last message
  timestamp `2026-02-07T06:01:41.279462Z` (unchanged).
- Flow:
  - evolved from ADR-vs-ingest framing into a stable engine/profile split.
  - moved normative ADR wording toward ingest-safe invariants/constraints.
  - refined compression from flat groups to declared lexical axes.
- Blockers:
  - ADR wording can reintroduce intent/authority leakage at Layer 0 ingest.
  - profile-specific terms can be mistaken for core engine behavior.
  - grouping can drift into implicit inference if not reversible and span-anchored.
- Progress:
  - engine/profile separation is now explicit and timestamp-verified.
  - actionable artifacts were queued in suite planning/TODO for
    `compression_engine.md`, profile contracts, lint rules, and cross-profile
    safety tests.

## Open questions
- Do we need richer fixtures for multi-verb phrases or nested scopes as we exercise S6 queries/views?
- Which consumers (CLI, API, Streamlit) should receive the first query/explanation surface?
- How should alignment reports surface metadata deltas without touching identity? (to be defined in S6.3)

## Chat mention scan (2026-02-03)
Ranked conversations by total mention frequency of: `SL`, `sensiblaw`, `ITIR`, `tircorder`, `tirc`.
Full ranking saved at `__CONTEXT/last_sync/mentions_rank_20260203_225730.tsv`.
Top 10 by total hits:
- 721 hits, 82 msgs: SENSIBLAW (thread `4d535d3f33f54b1040ab38ec67f8f550a0f69dce`)
- 637 hits, 49 msgs: Taxonomising legal wrongs (thread `74f6d0e08de82556df95c6ab1edb51557fede4fa`)
- 546 hits, 51 msgs: Feature timeline visualization (thread `f8170d36e0b2c28b2bb0366a7dc35a433e26ca00`)
- 308 hits, 22 msgs: Expand explanation request (thread `df662e5df0a444fa97e57053dd7c1cec130f9aeb`)
- 194 hits, 10 msgs: Data management ontology topology (thread `331a7d1304f329259315649e7a9d729a83b51daf`)
- 191 hits, 14 msgs: Aptos cryptocurrency overview (thread `32c691e2032f3ed787499254720081202500e94b`)
- 184 hits, 16 msgs: Actor table design (thread `21f55daa80206517e38f8c0fa56ee9bb2db8a9a0`)
- 163 hits, 15 msgs: Summary of key details (thread `cfacd6488919ade801d8137a9d05573ec31f9345`)
- 149 hits, 34 msgs: Research paper development (thread `15567e0112f953179e2ef6571de023b415d68bbb`)
- 141 hits, 23 msgs: Category coverage review (thread `83ee7436aa909dd31a14a147f10bb78cd52b6f55`)
Walkthrough notes saved at `__CONTEXT/last_sync/mentions_top10_walkthrough_20260203_230500.md`.
Quick walkthrough (top 10):
- SENSIBLAW: high-volume planning around ingesting/viewing Australian law, with explicit SL/ITIR/TiRCorder references.
- Taxonomising legal wrongs: ontology/taxonomy debate; TiRCorder and SL/ITIR framing recur as design anchors.
- Feature timeline visualization: README/vision work tying TiRCorder timeline views to SL/ITIR context.
- Expand explanation request: glossary/atom concepts, explanation surfaces, and actor/sentence-view needs.
- Data management ontology topology: distillation of ontology/topology spine for TiRC + SensibLaw integration.
- Aptos cryptocurrency overview: positioning SensibLaw/TiRC in institutional data/API/market comparisons.
- Actor table design: schema guidance on actors table boundaries and identity modeling.
- Summary of key details: competitive/positioning summaries, with SL vs others framing.
- Research paper development: steering research paper gaps and TiRCorder/ITIR priorities.
- Category coverage review: ML/graph category fit for SensibLaw/TiRCorder stack.
Selected walkthroughs (ranks 11, 14, 16-42, 44, 60, 67, 71-74, 78-81, 84-85):
- 11 Gary's YouTube strategy: SensibLaw feature-to-video mapping and marketing pipeline.
- 14 House v The King principles: PDF-to-principles/graph pipeline framed for SensibLaw/TiRCorder.
- 16 Timeline stream roadmap issue: coherence issues in timeline roadmap and prior rewrite log.
- 17 PDF to TiRCorder integration: integrating specific PDFs into TiRCorder pass.
- 18 SL Formalism Interpretation and Projection: formalism framing tied back to SensibLaw goals.
- 19 Design spec creation: request for developer-facing SensibLaw design spec.
- 20 Debates on causality: cross-domain debate/theory mapping with intermittent SL/TiRC framing.
- 21 Legal practice highlights: legal-practice relevance and SensibLaw burnout assistance.
- 22 Postgres vs alternatives for Rust: database choice rationale for SensibLaw stack.
- 23 Contributors needed for TiRCorder: project origin story and system coherence framing.
- 24 CI workflow optimization: GitHub Actions fixes for SensibLaw.
- 25 Key points summary: Wikitology summary with SL/TiRC reflection prompt.
- 26 Legal ethics and systems: legal-ethics discussion and briefing.
- 27 Oracle WHS compliance tool: comparison query referencing SensibLaw.
- 28 Ternary packing optimization: dashifine/ternary math discussion with SL/TiRC mentions.
- 29 Print principles list: PDF/JSON refinement plan for SensibLaw atoms.
- 30 Open-source contract analysis: SensibLaw positioned vs commercial contract tools.
- 31 Connect Codex to CDT: Codex CLI + Chrome DevTools connectivity.
- 32 TiRCorder goal summary: goal/acceptance bullets for rights-first TiRCorder.
- 33 Coles Palantir usage query: Palantir/system discussion with SL/TiRC mentions.
- 34 Balanced ternary systems: many-valued logic lineage tied to SensibLaw semantics.
- 35 Cannabis reforms Australia 2026: mixed content with incidental SL/TiRC mentions.
- 36 Table of contents processing: task backlog references for SensibLaw atom normalization.
- 37 Bitcoin value vs price drop: political-economic mapping with SL/TiRC ontology angle.
- 38 Key torts in Australia: tort taxonomy coverage with SL/TiRC references.
- 39 Boundary layer in law: boundary-layer framing for SensibLaw context.
- 40 Markdown table conversion: generic conversion task with SensibLaw mentions.
- 60 Taylor Swift politics: cultural critique + essay framing with SL/TiRC mentions.
- 67 Huawei patent explanation: ternary encoding note with SL/TiRC references.
- 71 Analyze FAQyMe Gene: request for direction on a pasted artifact mentioning SL/TiRC.
- 72 Idempotence and normalisation: spreadsheet + normalization note with SL/TiRC references.
- 73 Materialism vs Dialectics: brief context mention of ITIR.
- 78 StatiBaker Proposal: assistant concept spanning ITIR products and daily workflow.
- 79 OCR extraction and categorization: OCR extraction summary with SensibLaw mention.
- 80 Timeline prototype description: timeline prototype notes with ITIR mention.
- 85 Test computational efficiency: dashifine performance bottleneck note with SensibLaw mention.
Intersections with roadmap/todo/readme (2026-02-03):
- Repo `README.md`: submodule map matches chats spanning SensibLaw, SL-reasoner, TiRCorder, and WhisperX; the YouTube/roadmap/timeline threads align with cross-submodule integration framing.
- `ROADMAP.md`: focus on deterministic chat-history ingest into SQLite with SL/TIRC views overlaps with threads about ingest, explanation surfaces, timeline visualization, and cross-thread analysis.
- `SensibLaw/README.md`: shared TiRC + SensibLaw layered architecture aligns with ontology/taxonomy, actor table, PDF-to-graph, and timeline/claims discussions.
- `SensibLaw/todo.md`: S6 read-only deterministic surfaces and ingestion discipline align with explanation/trace requests, PDF integration, CI hardening, and schema/guardrail emphasis in the chats.

## Context update (2026-02-13)
- Requester TODO progression:
  - extractor-level `requester_coverage` counters already emitted,
  - AAO-all now uses those counters for `req:none` diagnostics in the context pane,
  - `req:none` selection now maps to missing requester event IDs so gap rows are inspectable,
  - follow-up TODO remains for automated UI assertions around requester-gap states.
- Projection lane progression:
  - AAO-all now includes dedicated non-role `Source` and `Lens` lanes,
  - those lanes are connected to actions via `context` overlay edges,
  - context rows now expose `sources` and `lenses` chips for traceability.
- Numeric lane/date boundary progression:
  - numeric extraction now suppresses month/day date fragments from numeric lanes
    even when spaCy labels the phrase as EVENT (`September 11`) instead of DATE,
  - slash-date fragments (`9/11`) are treated as temporal references and excluded
    from numeric lanes,
  - step numeric claim merge now respects sentence-allowed numeric keys to avoid
    re-injecting filtered date fragments,
  - AAO (`wiki-timeline-aoo`) numeric lane/context sorting is now magnitude-based
    (numeric key value + unit) instead of lexical.
- Ontology layering/taxonomy progression:
  - `docs/ontology.md` now includes a compressed liability-stack crosswalk
    (System/Source -> Abstract norm -> Doctrinal construction -> Event layer)
    mapped explicitly back to canonical L0-L6 entities to avoid layer-number drift.
  - WrongType modeling guidance now requires orthogonal dimensions beyond
    textbook labels (protected interest, mental state, interference mode, duty
    structure, remedy, defence).
  - Added `data/ontology/wrong_type_dimensions_seed.yaml` and regression checks
    in `tests/test_wrong_type_dimensions_seed.py` to keep dimension vocabularies
    deterministic and aligned with `wrong_type_catalog_seed.yaml`.

## Context update (2026-03-15)
- Source conversation: `Aptos cryptocurrency overview`
  - online UUID: `691ac8a3-4a30-8320-bd5f-f66efc3145e7`
  - canonical thread ID: `dff5b29b89818300e7e352c0247c4cef3823bcfd`
  - source used: `db` after direct UUID pull + ingest into `~/chat_archive.sqlite`
- Main Glasslane / Mirror decision pulled from the thread:
  - position SensibLaw/TiRC as the missing `human risk layer` for Mirror rather
    than as a competing crypto research assistant
  - Mirror's current strength is narrative intelligence for crypto research,
    compliance framing, and board-safe summaries
  - Mirror's gap is structured treatment of harms, obligations, money flows,
    behavioral patterns, and provenance over time
  - the joint pitch is: Mirror explains the crypto system; SensibLaw explains
    how crypto events affect actual people, obligations, and regulator/auditor
    workflows
  - additional thread-backed market read:
    - Mirror / Glasslane was being discussed as a tiny founder-led,
      early-stage, pre-PMF operation with a Discord/chatbot-first surface
      rather than as a mature institutional platform
    - the stated audience included investors, advisers, and accountants, but
      the visible community/community-growth posture looked closer to mixed
      retail + KOL + crypto-native participants
    - monetization ideas in the thread included NFT-gated access first and a
      token/community runway later, which reinforces the need to pitch
      SensibLaw/TiRC as the higher-trust provenance/governance layer
- Concrete product / feature concepts extracted from that thread:
  - `Crypto Consumer Harm Observatory (CCHO)`: distress/sentiment shifts,
    money-flow changes, harm-class triggers, obligation violations, and
    regulator-safe summaries around protocol/exchange/stablecoin events
  - `Risk & Behavioural Pattern Analytics` for exchanges/wallets: fraud,
    manipulation, economic abuse, predatory lending, and unusual
    relationship-level financial harm patterns
  - `High-Trust Explainability Layer` for boards/regulators: provenance-backed
    explanations of what happened, who was affected, what obligations arose,
    and where risk/harm is concentrating
  - API / integration posture: Glass/Mirror-like buyers will want stream
    endpoints, ingest connectors, cohort/product/time-window scores, and
    stable export surfaces rather than a UI-only tool
- Reusable cross-vertical packaging concept from the same thread:
  - Ribbon should remain the named surface; the common substrate is the
    Ribbon stream layer for timeline-aligned conserved / derived signals
  - thread examples included finance net/dependency, chat
    concern/control/empathy, and legal pressure / active obligations, but
    Ribbon itself remains a more general conserved-allocation timeline surface
  - change-point detection over those streams was framed as the core mechanism
    for surfacing pattern shifts without collapsing into unsupported verdicts
- SensibLaw-facing implication:
  - keep packaging the platform as an explainable evidence + obligations engine
    with vertical overlays, not as a monolithic "AI assistant"
  - for crypto/regtech partnerships, emphasize provenance, guardrails, and
    pattern detection over generic market commentary

## Sources
Chat-sourced statements are now referenced from the compression/ITIR overlay
discussion (see `698218f7-9ca4-83a1-969d-0ffc3d6264e4:1-80`).
Use `CONVERSATION_ID:line#` citing the line-numbered excerpts in
`__CONTEXT/last_sync/`.

## Context update (2026-03-28)
- Production schema/deployment bundle refinement:
  - added
    `docs/planning/itir_sensiblaw_postgres_schema_and_deployment_bundle_20260328.md`
    as the execution-oriented refinement of the current production pack
  - current repo-facing decision:
    - PostgreSQL is the reference production schema
    - SQLite/local-first still remains valid for the first single-user runtime
    - the reference bundle should stay explicit about:
      extensions/enums, dependency-ordered core tables, trigger helpers,
      operational views, deployment tiers, and dashboard roles
    - the first dashboard-facing SQL surfaces are:
      `vw_active_obligations`, `vw_sla_breaches`,
      `vw_traceability_coverage`, `vw_open_gaps`
    - the immediate production build order should remain bounded:
      core schema -> intake/evidence/atoms/signals/artifacts ->
      graph/gaps -> obligations/views -> audit/access -> optional sync/review
    - if implementation begins, prefer one bounded next artifact:
      migration-ready SQL in execution order or a local service/API spec over
      the same entity set
    - the schema/API refinement now also keeps explicit:
      migration ordering, `/api/v1` REST surface, and local worker-service
      split so the next implementation step can stay database-first or
      service-first without widening into full platform rollout
- Affidavit local-first proving slice decision:
  - added
    `docs/planning/affidavit_local_first_proving_slice_20260329.md`
  - current repo-facing decision:
    - use affidavit as the first SQLite/local-first proving slice for
      narrative integrity and evidence structure
    - keep tenancy as the later proving slice for obligation/SLA execution
    - do not create a parallel affidavit runtime; reuse the existing lane:
      `build_affidavit_coverage_review.py`,
      `persist_contested_affidavit_review(...)`,
      `fact_intake.read_model`, and `query_fact_review.py`
    - the immediate implementation target is one bounded read-model/workbench
      surface over persisted contested-review runs with grouped statuses and
      minimal next steps
  - implemented surface:
    - `build_contested_affidavit_proving_slice(...)` in
      `src/fact_intake/read_model.py`
    - `contested-proving-slice` query surface in
      `scripts/query_fact_review.py`
    - focused regression coverage in:
      `tests/test_affidavit_coverage_review.py`
      and `tests/test_query_fact_review_script.py`
  - proving-slice regrouping refinement:
    - `covered` remains sacred, but proving-slice grouping now also uses
      `best_response_role`, `support_status`, `support_direction`, and
      `conflict_state`
    - the grouped output now includes `weakly_addressed`
    - on the real Google Docs affidavit/response run this shifted the top-line
      read from:
      `supported 1 / missing 28 / needs_clarification 17 / disputed 0`
      to:
      `supported 1 / disputed 7 / weakly_addressed 36 / missing 2`
  - long-running live contested Google Docs builders now expose opt-in
    progress over:
    fetch, extract, grouping, proposition matching, artifact writing, and
    persistence, so slow forward movement is visible instead of looking hung
  - the same builders now also expose opt-in trace streaming for:
    proposition start, tokenization, top candidate selection, response packet
    inference, classification, semantic basis, and promotion result
  - next quality contract is now pinned as
    `docs/planning/affidavit_claim_reconciliation_contract_20260329.md`
  - current affidavit grouped resolver should now be treated as a bounded
    `v0` surface; the intended next improvement is relation-driven claim
    reconciliation with:
    normalized proposition/response fields, explicit relation types, dominant
    relation precedence, and bucket mapping derived from relation type rather
    than similarity alone
  - `weakly_addressed` should now be read as a transitional defect bucket, not
    a stable target class; the next classifier pass should split it into
    `partial_support`, `adjacent_event`, `substitution`, and
    `non_substantive_response`
  - minimum operator-facing explanation per proposition should become:
    classification, matched response, reason, and missing dimension
  - cross-lane priority is now explicit:
    affidavit claim reconciliation comes before further widening of
    `TEMP_zos_sl_bridge_impl`; the temp bridge remains second priority until
    it gains an explicit admissibility / acceptance boundary
  - first implementation followthrough is now landed in the proving-slice read
    model:
    it emits `relation_root`, `relation_leaf`, `explanation`, and
    `missing_dimensions`, and replaces the stable `weakly_addressed` section
    with explicit non-resolving subclasses
  - builder/persisted-row followthrough also landed:
    contested comparison rows now carry `relation_root`, `relation_leaf`,
    `primary_target_component`, `explanation`, and `missing_dimensions`
    before query-time fallback derivation
  - next quality boundary is now:
    duplicate-root and same-incident sibling-leaf handling across sides,
    with the live Johl affidavit / response pair as the primary Mary-parity
    fixture
  - interpretation:
    - cluster materially duplicate or near-duplicate John-side and Johl-side
      claims under one shared claim root or incident root
    - preserve side-local wording beneath that root
    - resolve support, qualification, contradiction, adjacent-event, and
      procedural framing at the leaf level
    - treat authority as local to the relation being shown, not one global
      winner for the whole cluster
- `2026-03-29` first duplicate-root affidavit followthrough:
  - updated `scripts/build_affidavit_coverage_review.py` so the builder can
    promote a duplicate or near-duplicate support clause ahead of a nearby
    contextual clause and now emits:
    - `claim_root_id`
    - `claim_root_text`
    - `claim_root_basis`
    - `alternate_context_excerpt`
  - added focused regression coverage in
    `tests/test_affidavit_coverage_review.py`
  - local validation passed:
    `cd /home/c/Documents/code/ITIR-suite && .venv/bin/python -m pytest -q SensibLaw/tests/test_affidavit_coverage_review.py SensibLaw/tests/test_query_fact_review_script.py`
    -> `35 passed`
  - live Johl rerun after that pass shifted the relation reading to:
    - `exact_support 1`
    - `equivalent_support 11`
    - `partial_support 7`
    - `explicit_dispute 6`
    - `adjacent_event 2`
    - `non_substantive_response 2`
    - `missing 22`
  - concrete result:
    - `p2-s38` and `p2-s39` now resolve as support via duplicate-root handling
    - `p2-s5` and `p2-s6` remain the next same-incident sibling-leaf failure
    - `p2-s21` still reads closer to adjacent event or substitution than true
      support
- `2026-03-30` affidavit matcher optimization pass v2:
  - `src/rules/dependencies.py` now caches dependency parses by repeated
    excerpt text
  - `scripts/build_affidavit_coverage_review.py` now memoizes tokenization,
    structural sentence analysis, lexical heuristic scans, and text splitting
    at the helper level
  - corrected `.venv` profile on the extracted Dad/Johl fixture:
    local build reduced from about `13.691s` to about `8.934s`
  - remaining dominant local cost is the parser call itself, so the next
    optimization boundary is parser amortization / lexical gating
- `2026-03-29` notebooklm-pack boundary check:
  - checked sibling repo `../notebooklm-pack` against the current `ZOS` /
    `JMD` notes
  - docs path status:
    `/home/c/Documents/code/kant-zk-pastebin/DOCS.md` exists as a symlink, but
    its target under `/home/mdupont/DOCS/...` is unavailable in this
    environment
  - main decision:
    `../notebooklm-pack` is only a repo-text collection and NotebookLM
    source-packing utility; it is not evidence for `ZOS <-> SL` semantics,
    `JMD` push/pull, admissibility, or proof/receipt boundaries
  - artifacts:
    - `../docs/planning/notebooklm_pack_zos_jmd_boundary_20260329.md`
    - `../README.md`
    - `../TODO.md`
- `2026-03-29` notebooklm-pack integration seam:
  - checked against the existing NotebookLM interfaces and observer docs
  - main decision:
    `../notebooklm-pack` fits as an upstream source-pack producer for
    NotebookLM source ingress, not as a semantic or bridge layer
  - preferred order:
    repo corpus -> notebooklm-pack -> notebooklm-py -> StatiBaker capture ->
    SensibLaw reuse
  - if implemented later, the first bounded seam should be a tiny wrapper or
    manifest-normalizer preserving pack run id, source file hash, contributing
    repos, and later NotebookLM notebook/source linkage
  - artifacts:
    - `../docs/planning/notebooklm_pack_to_notebooklm_py_interface_20260329.md`
    - `../README.md`
    - `../TODO.md`
- `2026-03-29` notebooklm-pack dry-run wrapper:
  - implemented the first bounded seam in `../scripts/notebooklm_pack_ingest.py`
  - current wrapper supports manifest normalization, source file hashing,
    deterministic `notebooklm` command planning, and optional live execution
    behind `--execute`
  - focused regression coverage landed in
    `../tests/test_notebooklm_pack_ingest.py`
  - live validation is now complete against the local authenticated NotebookLM
    environment
  - persistent validation notebook kept:
    `ITIR notebooklm-pack integration`
    (`ad2bbd9a-2c9c-47ee-a607-f2b735999d99`)
  - the next gap is not NotebookLM liveness; it is freezing the minimal seam
    object and keeping observer metadata separate from any future JMD receipt
    reading
- `2026-03-30` affidavit Phase 1 gate v3:
  - live Dad/Johl now runs on the SQLite-first inspection surface:
    - DB:
      `/tmp/dad_johl_phase1_gate_v3/itir.sqlite`
    - review run:
      `contested_review:b9d0cbbccb02c13e`
    - query surface:
      `scripts/query_fact_review.py contested-rows`
  - packet-local clause selection now keeps:
    - `p2-s5` on the intended audio-control clause
    - `p2-s6` on the intended keyboard-control clause
  - `p2-s21` remains on the EPOA revocation family with
    `relation_leaf = exact_support`
  - remaining live gap:
    `p2-s38` / `p2-s39` still reciprocally swap within the same
    quote-to-rebuttal row
- `2026-03-30` affidavit predicate-family routing pass:
  - matcher now keeps adjusted duplicate-root support rows even when their raw
    segment overlap is zero
  - live Dad/Johl artifact:
    `/tmp/dad_johl_predicate_family_v5/affidavit_coverage_review_v1.json`
  - current live target rows:
    - `p2-s5` -> intended audio row
    - `p2-s6` -> intended keyboard row
    - `p2-s21` -> intended EPOA revocation row
    - `p2-s38` / `p2-s39` stay in the improved same-incident sibling state
  - focused verification:
    `54 passed`
- `2026-03-30` affidavit SQLite-first runtime seam:
  - `scripts/build_affidavit_coverage_review.py` now supports persisted
    contested-review runs without bulky JSON/markdown outputs
  - `scripts/build_google_docs_contested_narrative_review.py` now accepts
    `--db-path` and defaults to SQLite-first live runs when it is supplied
  - bulky JSON/markdown affidavit review outputs are now explicit derived
    projections behind `--write-artifacts`
  - this makes the affidavit lane operationally consistent with
    `docs/planning/json_artifact_boundary_20260327.md`:
    persisted SQLite/read-model state is the working surface; JSON is receipt /
    export material
  - focused verification:
    `51 passed in 2.25s`
- `2026-03-30` affidavit Phase 1 milestone 1:
  - `scripts/query_fact_review.py contested-rows` now exposes a narrow
    SQLite-first row inspection seam over persisted contested-review runs
  - this is the first direct replacement for bulky artifact inspection in the
    Dad/Johl loop
  - `scripts/run_sl_with_zkperf.py` now supports command-mode observation from
    `--sl-db-path` alone, so DB-backed affidavit runs no longer need a fake
    JSON boundary just to be measured
  - `scripts/run_sl_zkperf_stream_hf.sh` now preserves the live
    `--sl-db-path ... -- COMMAND` path instead of degrading into static DB
    observation
  - focused verification:
    `SensibLaw/tests/test_query_fact_review_script.py` and
    `tests/test_sl_zkperf.py` passed
