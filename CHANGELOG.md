# 2026-04-19

- document the legal-follow pressure ownership split across `README.md`,
  `docs/interfaces.md`, and `todo.md`
- clarify that reusable pressure algebra is owned outside SensibLaw, while SL
  may only emit additive deterministic pressure metadata on derived legal-follow
  graph/review surfaces
- implement the first bounded typed legal-follow pressure payload in
  `src/policy/legal_follow_graph.py` and preserve it into the AU normalized
  artifact as `legal_follow_pressure`
- keep older string/score surfaces
  (`unresolved_pressure_status`, `priority_band_counts`,
  `highest_priority_score`)
  as separate workflow/readout channels rather than reusing them as the typed
  payload

# Changelog

## Unreleased
- Added `wikidata climate-review-demonstrator`, a bounded runtime report over
  the pinned `Q10403939` / Akademiska Hus climate packet. The command binds:
  - migration-pack candidate change surface
  - revision-locked climate text observations / claims
  - emitted bridge/residual comparison objects
  - final held/promotable disposition
  into one executable JSON artifact, without claiming broader Wikidata
  automation.
- Added
  [docs/planning/wikidata_climate_review_demonstrator_flow_20260429.puml](/home/c/Documents/code/ITIR-suite/SensibLaw/docs/planning/wikidata_climate_review_demonstrator_flow_20260429.puml)
  as the compact diagram companion to the new climate review demonstrator.
- Refreshed `docs/wikidata_working_group_status.md` so the live OCTF-facing
  status page points to the new runtime demonstrator and stops treating the
  `Q10403939` proof mostly as repeated prose.
- Added
  [docs/planning/wikidata_pnf_residual_review_example_20260429.md](/home/c/Documents/code/ITIR-suite/SensibLaw/docs/planning/wikidata_pnf_residual_review_example_20260429.md)
  as a bounded docs-first OCTF example. It uses the real `Q10403939`
  (`Akademiska Hus`) climate case to connect:
  - current migration-pack truth (`split_required`)
  - current text-bridge truth (`split_pressure`)
  - and the newer canonical-text / predicate-normal-form / residual framing
  without claiming a new executable Wikidata migration policy.
- Tightened the OCTF/Wikidata handoff docs so the LLM/governance language now
  matches the current predicate-normal-form, body-qualified extraction, and
  residual-lattice code paths more closely. The docs now say more precisely
  that:
  - LLMs, subclass checks, disjointness checks, and external ontologies are
    candidate-signal sources
  - the newer code makes the non-authoritative candidate layer and
    deterministic residual/gating surface more explicit
  - this strengthens the review/control boundary around the Wikidata lanes,
    without claiming a new Wikidata routing policy or broader automation
- AU legal-follow priority steering:
  - Extended `src/policy/legal_follow_graph.py` so derived legal-claim review
    packets are now ranked from structural `edge_admissibility` rows, and the
    operator summary exposes bounded priority rollups over the legal-follow
    queue.
  - Extended `src/fact_intake/review_bundle.py` so AU workflow guidance can
    recommend `legal_follow_graph` when legal-follow admissibility review
    pressure dominates promotion pressure.
  - Added focused coverage in `tests/test_legal_follow_graph.py` and
    `tests/test_au_fact_review_bundle.py`.
  - Validation:
    - from `SensibLaw/`:
      `PYTHONPATH=. ../.venv/bin/python -m pytest tests/test_legal_follow_graph.py tests/test_au_fact_review_bundle.py tests/test_latent_promoted_graph.py tests/test_cross_system_phi_prototype.py -q`
      -> `29 passed`
- AU legal-follow admissibility exposure:
  - Extended `src/policy/legal_follow_graph.py` so derived `asserts_*` edges
    now roll up into summary-level admissibility counts and one bounded
    `edge_admissibility_queue` for operator inspection.
  - Legal-claim reviewer packets now expose edge-admissibility detail rows
    without changing the derived-only ownership posture.
  - Extended `src/fact_intake/au_review_bundle.py` so AU bundle summaries now
    expose legal-follow edge-admissibility counts in both
    `semantic_context.legal_follow_graph.summary` and
    `operator_views.legal_follow_graph.summary`.
  - Added focused coverage in `tests/test_legal_follow_graph.py` and
    `tests/test_au_fact_review_bundle.py`.
  - Validation:
    - from `SensibLaw/`:
      `PYTHONPATH=. ../.venv/bin/python -m pytest tests/test_legal_follow_graph.py tests/test_au_fact_review_bundle.py tests/test_latent_promoted_graph.py tests/test_cross_system_phi_prototype.py -q`
      -> `26 passed`
- Derived legal-claim edge admissibility:
  - Updated `src/policy/legal_follow_graph.py` so derived `asserts_*` edges
    now carry typed `sl.legal_edge_admissibility.v1` output in edge metadata.
    Promoted-anchor reuse keeps the current owner surface, while lower-layer
    relation candidates remain auditable instead of looking silently promoted.
  - Extended `tests/test_legal_follow_graph.py` to pin both promoted-anchor
    reuse metadata and the candidate-edge audit path.
  - Updated `README.md` to pin the next bounded legal-graph step as typed
    edge-admissibility metadata on derived legal-claim edges, not a new
    promoted edge owner layer.
  - Validation:
    from `SensibLaw/`:
    `PYTHONPATH=. ../.venv/bin/python -m pytest tests/test_legal_follow_graph.py tests/test_latent_promoted_graph.py tests/test_cross_system_phi_prototype.py -q`
    -> `16 passed`
- Composed candidate review adapter:
  - Extended `src/policy/review_claim_records.py` with
    `build_review_candidate_from_composed_candidate_node(...)` so
    `sl.composed_candidate_node.v1` payloads can enter the existing
    `review_candidate` envelope without widening fact-intake or review-bundle
    contracts.
  - The adapter keeps the bridge non-promotive:
    - composed candidate node in
    - `review_candidate` out
    - no `target_proposition_id`
    - no promoted-output path
  - Added focused coverage in `tests/test_review_claim_records.py`.
  - Validation:
    `PYTHONPATH=SensibLaw ./.venv/bin/python -m pytest SensibLaw/tests/test_composed_candidate_node.py SensibLaw/tests/test_composed_candidate_admissibility.py SensibLaw/tests/test_review_claim_records.py -q`
    -> `30 passed`
- Legal edge admissibility gate:
  - Added `src/legal_edge_admissibility.py` as the first bounded structural
    edge gate above composed-candidate admissibility.
  - The gate evaluates typed `relation_kind`, endpoint admissibility inputs,
    wrapper/status compatibility, section/genre compatibility, shared support
    linkage, shared content identity where required, and structural
    status-conflict requirements for `contradicts` / `overrules`.
  - The gate remains fail-closed and non-lexical:
    raw text does not decide relation meaning or contradiction.
  - Added focused coverage in `tests/test_legal_edge_admissibility.py`.
  - Validation:
    `PYTHONPATH=SensibLaw ./.venv/bin/python -m pytest SensibLaw/tests/test_composed_candidate_node.py SensibLaw/tests/test_composed_candidate_admissibility.py SensibLaw/tests/test_review_claim_records.py SensibLaw/tests/test_legal_edge_admissibility.py -q`
    -> `38 passed`
- Promoted legal graph ownership:
  - Extended `src/latent_promoted_graph.py` and
    `schemas/sl.latent_promoted_graph.v1.schema.yaml` so promoted
    `review_relation` rows emit promoted `legal_claim` nodes plus typed
    `grounds_claim`, `claim_subject`, and `claim_object` edges.
  - Extended `src/policy/legal_follow_graph.py` so the AU legal-follow graph
    can reuse that promoted-anchor surface when present instead of rebuilding
    all legal claims from lower-layer candidates.
  - Added focused coverage in `tests/test_latent_promoted_graph.py` and
    `tests/test_legal_follow_graph.py`, while keeping
    `tests/test_cross_system_phi_prototype.py` green against the widened
    latent-graph schema.
  - Validation:
    from `SensibLaw/`:
    `PYTHONPATH=. ../.venv/bin/python -m pytest tests/test_latent_promoted_graph.py tests/test_legal_follow_graph.py tests/test_cross_system_phi_prototype.py -q`
    -> `15 passed`
- Composed candidate node + admissibility gate:
  - Added `src/models/composed_candidate_node.py`,
    `schemas/sl.composed_candidate_node.v1.schema.yaml`, and
    `examples/composed_candidate_node_minimal.json` as the first bounded
    contract for candidate nodes above minimal `Phi` emissions.
  - Added `src/composed_candidate_admissibility.py` as a fail-closed
    node-level gate returning `promote | audit | abstain` from provenance,
    wrapper, slot/content, section/genre, and accepted-constraint checks.
  - Exported the composed-candidate helpers through `src/models/__init__.py`.
  - Added focused coverage in
    `tests/test_composed_candidate_node.py` and
    `tests/test_composed_candidate_admissibility.py`.
  - Validation:
     `PYTHONPATH=SensibLaw ./.venv/bin/python -m pytest SensibLaw/tests/test_composed_candidate_node.py SensibLaw/tests/test_composed_candidate_admissibility.py -q`
     -> `10 passed`
  - Added provider-backed ontology enrichment helpers on the normalized
    `src/ontology` surface, including candidate lookup, deterministic
    filtering, JSON emission, and optional interactive upsert into the existing
  concept/actor external-reference tables.
- Documented the enrichment boundary in `docs/external_ontologies.md` so the
  new helpers stay advisory and do not create a parallel ontology package.
- Affidavit Phase 1 gate v3:
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
- Affidavit matcher optimization pass v2:
  - Updated `src/rules/dependencies.py` so repeated excerpt texts reuse cached
    dependency parses instead of re-running the parser path each time.
  - Updated `scripts/build_affidavit_coverage_review.py` so tokenization,
    structural sentence analysis, lexical heuristic scans, and text splitting
    are memoized at the helper level.
  - Added focused coverage in `tests/test_affidavit_coverage_review.py` for
    contested quote-to-rebuttal matching behavior while keeping the broader
    focused suites green.
  - Corrected `.venv` profiling on the extracted Dad/Johl fixture now shows the
    local build path reduced from about `13.691s` to about `8.934s`.
  - Remaining dominant local cost is the spaCy parse itself, so the next
    optimization target is parser amortization / lexical gating rather than
    more generic regex caching.
- notebooklm-pack dry-run wrapper:
  - Added `../scripts/notebooklm_pack_ingest.py` as the first bounded
    integration seam between sibling `notebooklm-pack` output and the repo’s
    existing `notebooklm-py` push/pull surface.
  - The wrapper normalizes `manifest.json`, computes source file hashes, emits
    `pack_run` plus `packed_sources` linkage records, and produces a
    deterministic `notebooklm` command plan with optional live execution behind
    `--execute`.
  - Added focused regression coverage in
    `../tests/test_notebooklm_pack_ingest.py`.
  - Live validation now succeeded against the local authenticated NotebookLM
    environment, including notebook creation, source upload, source wait, and
    source/artifact/status listing.
  - Fixed real live mismatches in the wrapper:
    nested notebook/source JSON response shapes, unsupported
    `source wait --interval`, and local CLI discovery from the repo `.venv`.
  - Kept a persistent validation notebook:
    `ITIR notebooklm-pack integration`
    (`ad2bbd9a-2c9c-47ee-a607-f2b735999d99`)
    with seeded linkage artifacts stored under the root repo
    `.cache_local/notebooklm_pack_runs/20260329_persistent_integration_seed/`.
  - Updated `../docs/planning/notebooklm_pack_to_notebooklm_py_interface_20260329.md`,
    `../docs/planning/jmd_notebooklm_seam_minimal_object_20260329.md`,
    `../TODO.md`, `../COMPACTIFIED_CONTEXT.md`, and
    `COMPACTIFIED_CONTEXT.md` so the repo now records the live success and the
    next JMD question as seam-object disambiguation rather than NotebookLM
    liveness.
- notebooklm-pack to notebooklm-py interface note:
  - Added `../docs/planning/notebooklm_pack_to_notebooklm_py_interface_20260329.md`
    to define the clean integration seam between the sibling Rust packer and
    the repo’s existing NotebookLM interfaces.
  - Recorded the intended order as:
    repo corpus -> notebooklm-pack -> notebooklm-py -> StatiBaker capture ->
    SensibLaw reuse.
  - Updated `../README.md`, `../TODO.md`, `../COMPACTIFIED_CONTEXT.md`, and
    `COMPACTIFIED_CONTEXT.md` so later implementation stays scoped to a small
    source-ingest wrapper or manifest-normalizer rather than a semantic
    bridge.
- notebooklm-pack boundary check:
  - Added `../docs/planning/notebooklm_pack_zos_jmd_boundary_20260329.md`
    after checking the new sibling `../notebooklm-pack` repo against the
    current `ZOS` / `JMD` notes.
  - Recorded that the pack is a bounded NotebookLM source-packing utility, not
    evidence for `ZOS <-> SL` semantics, JMD push/pull, admissibility, or
    proof/receipt boundaries.
  - Updated `../README.md`, `../TODO.md`, `../COMPACTIFIED_CONTEXT.md`, and
    `COMPACTIFIED_CONTEXT.md` so later work keeps that boundary explicit.
- Affidavit duplicate-root builder followthrough:
  - Updated `scripts/build_affidavit_coverage_review.py` so the builder now
    promotes duplicate or near-duplicate support clauses ahead of nearby
    contextual clauses and emits `claim_root_id`, `claim_root_text`,
    `claim_root_basis`, and `alternate_context_excerpt` on affidavit rows.
  - Added focused regression coverage in
    `tests/test_affidavit_coverage_review.py`.
  - Reran the live Johl Google Docs pair after the first bounded
    duplicate-root pass; `p2-s38` and `p2-s39` now resolve as support, while
    `p2-s5` and `p2-s6` remain the next same-incident sibling-leaf
    cross-swap gap and `p2-s21` still reads closer to adjacent event or
    substitution than true support.
  - Updated `../docs/planning/affidavit_claim_reconciliation_contract_20260329.md`,
    `../docs/planning/affidavit_coverage_review_lane_20260325.md`,
    `../TODO.md`, `../COMPACTIFIED_CONTEXT.md`, and
    `COMPACTIFIED_CONTEXT.md` so the repo now records that the first
    duplicate-root followthrough is landed and that sibling-leaf handling is
    the next affidavit-lane quality boundary.
- Affidavit duplicate-root and Mary-parity planning alignment:
  - Updated `docs/planning/affidavit_claim_reconciliation_contract_20260329.md`, `docs/planning/affidavit_coverage_review_lane_20260325.md`, and `docs/planning/mary_parity_user_story_acceptance_matrix_20260315.md` to record the next affidavit-lane quality boundary as duplicate-root and same-incident sibling-leaf reconciliation across sides, with the live Johl affidavit / response pair treated as the primary Mary-parity fixture.
  - Updated `TODO.md`, `COMPACTIFIED_CONTEXT.md`, and `SensibLaw/COMPACTIFIED_CONTEXT.md` so the repo now prioritizes shared-root clustering, side-local leaf relations, and typed local authority reading ahead of broader substitution widening.
- Affidavit relation-classifier followthrough:
  - Updated `src/fact_intake/read_model.py` so the contested affidavit proving-slice lane now computes explicit typed relations (`relation_type`) with subject/action/polarity-aware checks and derives final section bucketing from that relation output instead of leaning only on coverage/support heuristics.
  - The proving-slice rows now consistently expose `relation_type`, `relation_root`, `relation_leaf`, `explanation`, and `missing_dimensions`, including re-derivation when persisted rows do not yet carry the richer fields.
  - Updated `tests/test_query_fact_review_script.py` to assert relation-type and classification behavior on the `contested-proving-slice` query surface.
- Revision-locked climate text producer for Wikidata `Phi` bridge:
  - Added `schemas/sl.wikidata.climate_text_source.v1.schema.yaml` as the
    bounded source contract for the first real text-side producer in the
    `P5991 -> P14143` review lane.
  - Added runtime helpers in `src/ontology/wikidata.py`:
    - `build_observation_claim_payload_from_revision_locked_climate_text_sources(...)`
    - `attach_wikidata_phi_text_bridge_from_revision_locked_climate_text(...)`
  - Extended `scripts/materialize_wikidata_migration_pack.py` with optional
    climate-text input/output flags so one run can now emit both the derived
    Observation/Claim payload and the bridge-enriched migration pack.
  - Added focused coverage in:
    - `tests/test_wikidata_projection.py`
    - `tests/test_materialize_wikidata_migration_pack.py`
  - Recorded the current live target-selection result:
    `HSBC` / `Q190464` is not a valid target for the `P5991 -> P14143` lane
    right now because it does not currently expose live `P5991`, so the first
    non-fixture text artifact should pivot to already-pinned climate-pack
    entities instead.
  - Added the first non-fixture climate text artifact at
    `data/ontology/wikidata_migration_packs/p5991_p14143_climate_pilot_20260328/climate_text_source_q10403939_akademiska_hus_scope1_2018_2020.json`
    using official Akademiska Hus annual report excerpts from 2018, 2019, and
    2020.
  - Validated the artifact against `sl.wikidata.climate_text_source.v1`,
    converted it into `3` promoted observations / claims, and ran it through
    the current bridge against the pinned five-entity climate pack.
  - Current real-source result:
    before the temporal matcher fix, all `24` current `Q10403939`
    candidates received `contradiction` pressure from the older scope-1 text
    slice against the current 2023 multi-scope structured bundle.
  - Added period-aware mismatch gating in `src/ontology/wikidata.py` so
    out-of-period text observations no longer collapse straight to hard
    contradiction when the structured bundle carries a different explicit year
    slice.
  - Added focused regression coverage in
    `tests/test_wikidata_projection.py` for out-of-period value mismatches.
  - Re-running the real `Q10403939` artifact now yields `split_pressure` on
    all `24` candidates instead of `contradiction`, which better matches the
    intended review semantics.
  - Added a generic revision-locked `sl.source_unit.v1` schema at
    `schemas/sl.source_unit.v1.schema.yaml` plus a `SourceUnitAdapter`-style
    runtime path in `src/ontology/wikidata.py`.
  - Kept `sl.wikidata.climate_text_source.v1` working as a backward-compatible
    legacy subtype by adapting it into the generic source-unit payload before
    extraction.
  - Added focused coverage showing the same extractor/bridge path now accepts
    both legacy climate payloads and HTML snapshot source units.
- Boundary-artifact / morphism framing:
  - Added `docs/planning/boundary_artifact_morphism_contract_20260328.md` to
    pin the next higher docs-first formalism above the current boundary object
    family.
  - Recorded the current decision that `SourceUnit`, `SplitPlan`,
    `EventCandidate`, affidavit comparison artifacts, and affect overlays are
    now real enough to treat as a shared boundary-artifact family.
  - Kept runtime unification deferred:
    the repo now documents governed morphisms and composition rules as the next
    abstraction, but does not yet introduce a shared transformation engine.
  - Tightened that note with the first concrete candidate next layer:
    `BoundaryArtifact.v1`, `Morphism.v1`, a bounded composition validator, and
    a small readable transformation DSL, still as docs-first planning only.
- Cross-system `Phi_meta` tightening:
  - Recorded that `Phi_meta` is already shipped as a bounded executable layer,
    so the next useful step is a concrete example instance plus a bounded
    real-data prototype rather than another abstract schema rewrite.
  - Made the lane split explicit:
    the Wikidata climate lane still points at `source_capture -> SourceUnit`,
    while the cross-system legal lane now points at the bounded two-system
    prototype as its next optimal move.
- ITIR / SensibLaw receipts-first compiler spine:
  - Added
    `docs/planning/itir_sensiblaw_receipts_first_compiler_spine_20260328.md`
    to pin the strongest shared architectural reading across the current ITIR
    and SensibLaw materials.
  - Recorded the five-layer split:
    source substrate -> deterministic extraction -> promotion -> reasoning ->
    public-action packaging.
  - Recorded the main architectural rule that promotion is the center of the
    system, while graph reasoning and public packaging remain downstream of
    promoted truth.
  - Synced root `TODO.md` and compact context so the next milestone is
    explicit:
    one bounded doctrine prototype that proves the whole receipts-first spine
    end to end.
- ITIR / SensibLaw identity-trust alignment refinement:
  - Added
    `docs/planning/itir_sensiblaw_identity_trust_alignment_layer_20260328.md`
    to record the stronger reading that the suite must bridge lived
    experience, evidence, formal rules, and trust-preserving action rather
    than acting as only a legal compiler.
  - Tightened the receipts-first compiler spine note so the first bounded
    doctrine prototype is now expected to be not only receipt-backed but also
    explicitly non-gaslighting and trust-preserving in presentation.
  - Synced root `TODO.md` and compact context so the stronger requirement is
    durable repo state:
    trustworthy, non-gaslighting support without forcing the user to restate
    the whole story from scratch.
- Refreshed `ZKP for ITIR SensibLaw` online thread sync:
  - Pulled online UUID `69c7b950-daec-839d-89a9-8fd8e22c9136` into the
    canonical archive and resolved it to canonical thread ID
    `31a47318f53b61cac9f82705e2595b1a08f9af66` from the DB.
  - Added
    `docs/planning/itir_sensiblaw_operational_readiness_overlay_20260328.md`
    to record the next maturity gap above the current compiler spine:
    service-level definitions, incident vs problem handling, measurable
    success criteria, and explicit system-boundary / handoff views.
  - Synced root `TODO.md` and compact context so those readiness gaps are
    durable repo state instead of chat-only guidance.
  - Fixed a local refactor regression in `scripts/chat_context_resolver.py`
    where stale `_truncate_text` references broke DB-backed UUID resolution
    after the helper extraction pass.
- ITIR / SensibLaw standard service application model:
  - Added
    `docs/planning/itir_sensiblaw_standard_service_application_model_20260328.md`
    to pin the repeatable application pattern for new case families above the
    existing compiler-spine and trust/readiness notes.
  - Recorded the standard case flow:
    intake -> evidence structuring -> identity/context modelling -> alignment
    -> obligation assignment -> output -> monitoring/escalation.
  - Synced root `TODO.md` and compact context so the next doctrine prototype
    is now expected to carry a standardized intake shape, a mandatory
    obligation layer, a nonconformance grammar, and a minimal metric set
    rather than being argued case by case.
- ITIR / SensibLaw everyday mode:
  - Added `docs/planning/itir_sensiblaw_everyday_mode_20260328.md` to pin the
    lighter operating mode for ordinary, low-stakes scenarios without
    splitting the architecture into a second system.
  - Recorded the operating-mode rule:
    same architecture, different thresholds/defaults/surface area, with
    everyday mode biased toward guidance and next-best-action output rather
    than proof-heavy packaging.
  - Synced root `TODO.md` and compact context so the next explicit design gap
    is bounded switching criteria between crisis/adversarial mode and
    everyday/navigation mode.
- ITIR / SensibLaw case-type libraries + KPI model:
  - Added
    `docs/planning/itir_sensiblaw_case_type_libraries_and_kpi_model_20260328.md`
    to define the next service layer above the standard flow:
    fixed-shape case libraries plus a shared KPI model.
  - Recorded the first four libraries supported by the current corpus:
    tenancy, abuse/accountability, medical/trauma-informed care,
    welfare/support.
  - Synced root `TODO.md` and compact context so the next bounded prototype is
    now expected to choose one concrete library and one minimal KPI slice
    instead of staying fully generic.
- ITIR / SensibLaw diagrams + mode-switching / UI / templates:
  - Added
    `docs/planning/itir_sensiblaw_service_architecture_plantuml_20260328.puml`
    as the repo-owned PlantUML bundle for the system context, containers,
    standard flow, four case libraries, and obligation sequence.
  - Added
    `docs/planning/itir_sensiblaw_mode_switching_ui_and_templates_20260328.md`
    to define the next product-layer refinement:
    bounded mode switching, everyday UI flow, and common ordinary-user
    templates.
  - Tightened that note with a deterministic trigger reading over risk,
    time pressure, conflict level, evidence completeness, trust state, and
    user intent, plus a simple mode decision matrix and behavioral
    differences between light and strict operation.
  - Added explicit everyday screen and tone structure guidance along with
    always-on guardrails:
    no identity assertions without evidence, no moralizing language,
    no hidden assumptions, abstain when uncertain, local-first by default.
  - Extended the same note with concrete light-to-strict scenario templates
    for work/manager conversations, email/communication, tenancy friction,
    money/bills, health/appointments, personal planning, and low-to-high
    conflict.
  - Added starter mode/UX/safety KPIs and documented the `Mode Controller`
    placement in the container/application view so mode is treated as an
    explicit control surface rather than a hidden UI toggle.
  - Consolidated the same note further with the product-spec surface for the
    mode controller itself:
    inputs, outputs, deterministic logic, behavior profiles, trust controls,
    and the core `Obligation` primitive.
  - Extended the PlantUML bundle with explicit mode-controller alignment and
    everyday UX-flow diagrams so the controller and light/strict UX paths are
    visible in the architecture artifacts.
  - Added compact PlantUML variants for context, container, mode selection,
    standard flow, and obligation lifecycle so the architecture now has both
    concise and expanded diagram views in one repo-owned bundle.
  - Added the final system summary to the mode/UI note:
    the suite is now documented not only as a thinking aid but as a
    controlled service that turns human situations into structured,
    actionable, accountable outcomes.
  - Synced root `TODO.md` and compact context so the next design gap is now
    explicit:
    define the switch table and starter everyday template set before widening
    normal-user scope further.
- ITIR / SensibLaw production schema / dashboard / deployment pack:
  - Added
    `docs/planning/itir_sensiblaw_production_schema_dashboard_deployment_pack_20260328.md`
    to define the next production-facing contract layer for entities,
    dashboards, and local-first deployment.
  - Recorded the first production entity set, the three-layer dashboard split,
    and the staged local-first deployment topology:
    local single-user runtime first, optional trusted sync second, restricted
    collaboration later.
  - Synced root `TODO.md` and compact context so the immediate production
    validation target is now explicit:
    validate a local-first single-user case engine with truth-status states,
    obligation object, and dashboard surfaces before attempting full
    collaboration-platform scope.
- Shared proposal-layer framing:
  - Added
    `docs/planning/proposal_artifact_contract_v1_20260328.md`
    as a docs-first shared contract above domain-specific proposal artifacts.
  - Corrected the initial framing so it now treats Wikidata `SplitPlan` and
    fact-intake `EventCandidate` as the first two already-existing mapped
    subtypes, with the affidavit review lane as the cross-domain stress test,
    instead of implying the repo was still waiting for a second subtype.
  - Synced `docs/planning/wikidata_split_plan_contract_20260328.md`,
    `docs/wikidata_working_group_status.md`, `COMPACTIFIED_CONTEXT.md`, and
    root `TODO.md` so the repo now treats runtime unification as deferred for
    value/fit reasons rather than lack of concrete proving grounds.
- Refreshed doctrine sync from live context:
  - Recorded the broader all-sources `FactBundle` /
    reconciliation direction as the next generalization target above the
    current `Observation` / `Claim` seam, while keeping Wikidata and other
    projection lanes downstream of that canonical fact layer.
  - Recorded the refreshed boundary that sentiment/affect remains
    speaker/utterance-anchored candidate or overlay material and does not
    become canonical legal truth or dashboard authority.
  - Synced `COMPACTIFIED_CONTEXT.md` and root planning/TODO surfaces to match
    those refreshed boundaries.
- Wikidata `Phi` text-bridge executable slice:
  - Added
    `schemas/sl.wikidata_phi_text_bridge_case.v1.schema.yaml`
    and runtime helpers in `src/ontology/wikidata.py`:
    `build_wikidata_phi_text_bridge_case(...)` and
    `attach_wikidata_phi_text_bridge(...)`.
  - Extended `sl.wikidata_migration_pack.v1` and
    `build_wikidata_migration_pack(...)` with additive bridge fields:
    `bridge_cases`, `text_evidence_refs`, `bridge_case_ref`, `pressure`,
    `pressure_confidence`, and `pressure_summary`.
  - Added the first real producer adapter from
    `sl.observation_claim.contract.v1` into the bridge via:
    `extract_phi_text_observations_from_observation_claim_payload(...)` and
    `attach_wikidata_phi_text_bridge_from_observation_claim(...)`.
  - Added focused regression coverage in
    `tests/test_wikidata_projection.py` for:
    - default empty bridge state
    - `split_pressure` from promoted temporal text observations
    - `contradiction` pressure attachment to migration-pack rows
    - Observation/Claim contract -> bridge -> migration-pack integration
- Wikidata `Phi` text-bridge planning:
  - Added
    `docs/planning/wikidata_phi_text_bridge_contract_20260328.md`
    to define the bounded bridge between current migration-pack rows and any
    future promoted text-observation lane.
  - Updated the climate protocol note, migration-pack contract, working-group
    status, root `TODO.md`, and `COMPACTIFIED_CONTEXT.md` so the next-step
    rule is explicit:
    text may add promoted evidence and bounded `pressure`
    (`reinforce`, `split_pressure`, `contradiction`, `abstain`), but must not
    bypass promotion or directly override the structured migration baseline.
- Wikidata migration-pack split/action refinement:
  - Extended `src/ontology/wikidata.py` so temporal/multi-value `P5991`
    statement bundles can graduate from coarse ambiguity into
    `split_required` using bounded structural heuristics over temporal
    qualifiers and sibling statement layout.
  - Generalized that split logic so it is now property-agnostic:
    detect independent axes over the bundle/sibling context and emit them as
    `split_axes` on each candidate row.
  - Added a narrow candidate-level action field to `MigrationPack` rows:
    `migrate`, `migrate_with_refs`, `split`, `review`, or `abstain`.
  - Extended the OpenRefine CSV export to surface that action explicitly.
  - Updated `schemas/sl.wikidata_migration_pack.v1.schema.yaml`,
    `tests/test_wikidata_projection.py`, and `tests/test_wikidata_cli.py`.
  - Rebuilt the pinned `P5991 -> P14143` climate pilot pack from the existing
    bounded slice so `migration_pack.json` now reflects the split-aware
    runtime:
    - `safe_with_reference_transfer`: 1
    - `split_required`: 56
  - Added `sensiblaw wikidata export-migration-pack-checked-safe` as the first
    execution-adjacent export surface over only the already-safe subset.
  - Added `sensiblaw wikidata verify-migration-pack` as a bounded after-state
    verifier over the checked-safe subset, with statuses for exact success,
    duplicates, drift, and missing targets.
  - Added `sensiblaw wikidata build-split-plan` plus
    `schemas/sl.wikidata_split_plan.v0_1.schema.yaml` and
    `docs/planning/wikidata_split_plan_contract_20260328.md`
    as the first review-only `1 -> N` split artifact for structurally
    decomposable `split_required` slots.
  - Synced the migration contract, climate protocol note, working-group
    status, `COMPACTIFIED_CONTEXT.md`, and root `TODO.md` so docs now match
    the runtime split/action boundary.
- Wikidata climate-migration operator boundary refinement:
  - Updated
    `docs/planning/wikidata_climate_change_property_migration_protocol_20260327.md`,
    `docs/planning/wikidata_migration_pack_contract_20260328.md`, and
    `docs/wikidata_working_group_status.md`
    to make the plain-language operator boundary explicit:
    the current lane performs structured statement-bundle checks, not
    source-text reasoning.
  - Recorded the immediate next goal as a better action model for
    temporal/multi-value rows, starting with `split_required`, rather than
    overstating the current lane as a migration executor.
- Typed latent graph over promoted relations:
  - Added `src/latent_promoted_graph.py` and
    `schemas/sl.latent_promoted_graph.v1.schema.yaml` for the first bounded
    executable `L(P)` graph slice over promoted relation records.
  - Added focused coverage in `tests/test_latent_promoted_graph.py`.
  - Extended `src/cross_system_phi.py`,
    `schemas/sl.cross_system_phi.contract.v1.schema.yaml`, and
    `examples/cross_system_phi_minimal.json` so `Phi` payloads now expose
    graph summaries and per-mapping latent graph refs tied to the same
    promoted-record basis.
- `Phi` witness/explanation enrichment:
  - Extended `src/cross_system_phi_meta.py` so validation now emits explicit
    witness objects for type, role, authority, constraint, and scope checks.
  - Extended `src/cross_system_phi.py` and
    `schemas/sl.cross_system_phi.contract.v1.schema.yaml` so admitted mappings
    now emit `mapping_explanation` with structured witness detail.
  - Updated `examples/cross_system_phi_minimal.json` and regression tests in
    `tests/test_cross_system_phi_meta.py` and
    `tests/test_cross_system_phi_prototype.py`.
- `Phi_meta` admissibility layer:
  - Added `schemas/sl.cross_system_phi_meta.v1.schema.yaml` and
    `src/cross_system_phi_meta.py` as the bounded admissibility/type gate for
    cross-system mapping.
  - Extended `src/cross_system_phi.py` and
    `schemas/sl.cross_system_phi.contract.v1.schema.yaml` so current
    cross-system payloads emit `meta_validation` receipts and explicit blocked
    candidate rows before `Phi_ij` runs.
  - Added focused coverage in
    `tests/test_cross_system_phi_meta.py` and updated
    `tests/test_cross_system_phi_prototype.py`.
- Cross-system `Phi` promoted-record prototype:
  - Added `src/cross_system_phi.py` to build the bounded
    `sl.cross_system_phi.contract.v1` payload over real promoted relations
    emitted by existing semantic pipelines.
  - Extended `schemas/sl.cross_system_phi.contract.v1.schema.yaml` with an
    explicit provenance-preservation rule, provenance index, and mismatch
    workflow metadata.
  - Kept `examples/cross_system_phi_minimal.json` aligned with the extended
    contract and added real promoted-report regression coverage in
    `tests/test_cross_system_phi_prototype.py`.
- Docs: bounded climate-change property-migration protocol
  - Added `docs/planning/wikidata_climate_change_property_migration_protocol_20260327.md`
    to define how the repo's existing Wikidata review stack should be applied
    to real property-migration questions, anchored on the current
    `P5991 -> P14143` climate-change case.
  - Synced `docs/wikidata_working_group_status.md`, root `TODO.md`, and
    `COMPACTIFIED_CONTEXT.md` so the new lane is explicit:
    bounded candidate slice first, statement-bundle comparison, revision-window
    review, migration buckets, and no bot/export surface before a checked-safe
    subset exists.
  - Tightened that note with a ZKP framing of `Wikipedia:WikiProject Climate
    change`: treat the WikiProject as an upstream proposal/coordination layer
    and noisy substrate, not as the semantic truth layer, admissibility
    lattice, or migration engine.
  - Updated the migration docs/context to make the current operator boundary
    explicit:
    - full-set classification/filtering is already useful
    - full migration execution is not yet a trustworthy claim
    - the pinned pilot's heavy `ambiguous_semantics` share is the main current
      blocker to presenting the lane as final-output ready
  - Synced the literature-backed framing so Rosario, Ege/Peter, and Zhao/Takeda
    are used to support review/test/inspection positioning rather than
    end-to-end automation claims.
  - Extended the note with a formal cross-system mapping
    `Φ : W × Π × Κ → L(P)`, a factored ingest/extract/normalize/bundle/
    classify/promote/graph pipeline, and an explicit `L(P)` climate-article
    graph schema with constraints/invariants for provenance, controversial-topic
    guards, abstention, bundle integrity, bounded-slice gating, and
    bot-before-safe-subset prevention.
- Wikidata MigrationPack v0.1:
  - Added the first executable migration-pack contract note:
    `docs/planning/wikidata_migration_pack_contract_20260328.md`
    plus schema:
    `schemas/sl.wikidata_migration_pack.v1.schema.yaml`.
  - Extended `src/ontology/wikidata.py` with:
    - `MIGRATION_PACK_SCHEMA_VERSION`
    - reference-signature/property-set aggregation
    - slot-level `reference_drift`
    - `build_wikidata_migration_pack(...)`
  - Extended `sensiblaw wikidata` with the new
    `build-migration-pack` subcommand for bounded source->target property
    review packs.
  - Added regression coverage in
    `tests/test_wikidata_projection.py` and
    `tests/test_wikidata_cli.py`.
  - Added `scripts/materialize_wikidata_migration_pack.py` to fetch a bounded
    revision-locked live entity set, persist raw entity exports, and emit the
    derived slice + migration pack together.
  - Extended the live materializer so it can either:
    - consume an explicit QID set (`--qid`, `--qid-file`), or
    - discover a bounded live sample from the source property
      (`--discover-qids --candidate-limit N`)
    and record the exact selected QIDs in the emitted manifest.
  - Added the first OpenRefine bridge:
    `sensiblaw wikidata export-migration-pack-openrefine`
    which exports `MigrationPack` JSON to flat CSV with bucket, drift,
    confidence, and review columns for operator faceting.
  - Extended `scripts/materialize_wikidata_migration_pack.py` with
    `--openrefine-csv` so a single run can now discover/accept QIDs,
    materialize the bounded pack, and emit the OpenRefine review CSV.
  - Pinned the first live climate pilot pack in:
    `data/ontology/wikidata_migration_packs/p5991_p14143_climate_pilot_20260328/`
    using Q56404383, Q10651551, Q10416948, Q10403939, and Q10422059.
  - Corrected migration-pack evidence gating so normal-rank statements with
    actual reference evidence are reviewable; gating now follows evidence
    presence instead of non-zero `tau`.
  - The first live pilot currently yields:
    - `safe_with_reference_transfer`: 2
    - `ambiguous_semantics`: 55
- Milestone R temporal/jurisdiction parity for Wikidata projection:
  - Extended `src/sl_projection_boundary.py` so `build_wikidata_projection_report(...)`
    includes per-record temporal scope and transition-receipt provenance, plus
    jurisdiction-aware projection summary counters.
  - Updated `schemas/sl.observation_claim.wikidata_projection.v1.schema.yaml` to
    make `state_transition_receipt_ids`, `temporal_scope`, and corresponding
    summary counters schema-valid.
  - Added assertions in
    `tests/test_observation_claim_wikidata_projection.py` covering temporal
    scope, transition receipts, and jurisdiction provenance in the projection
    output.
  - Expanded projection rows to include `state_transition_receipts` payload fields
    (`jurisdiction`, `legal_version`, `effective_from`, `effective_to`,
    `rule_version`) for deterministic auditability.
  - Added projection-time validation that claim-level jurisdiction and legal
    norm context align with attached transition receipts; mismatches now fail
    fast before emission and are covered by regression tests.
- Milestone R contract definition:
  - Added a bounded machine contract for Observation/Claim/evidence-link payloads:
    `schemas/sl.observation_claim.contract.v1.schema.yaml`.
  - Linked the contract from
    `docs/planning/sl_observation_claim_contract_20260327.md` so milestone R
    contract definition now has a runtime-validatable schema surface.
- Cross-source follow/review control plane:
  - Added `src/fact_intake/control_plane.py` with the first portable
    `follow.control.v1` contract for operator queues:
    `control_plane`, normalized `queue` items, route-target counts, and
    resolution-status counts.
  - Generic fact-review workbench views now expose that control plane on
    `operator_views.intake_triage` and `operator_views.contested_items`.
  - AU `operator_views.authority_follow` now emits the same portable
    control-plane metadata and normalized queue items while preserving its
    richer authority-specific detail.
  - Added regression coverage in `tests/test_fact_intake_read_model.py`,
    `tests/test_query_fact_review_script.py`, and
    `tests/test_au_fact_review_bundle.py`.
- AU semantic/fact-review can now reuse persisted authority receipts
  - Extended `src/au_semantic/semantic.py` with a default-on
    `authority_receipts` semantic-context lane that links persisted
    `authority_ingest` receipts back to AU linkage/event authority hints
    without performing live follow.
  - That lane now emits a lightweight authority substrate summary per receipt
    (source identity, selected paragraphs, selected segment previews/kinds,
    linked event sections, linked authority signals, extracted neutral
    citations / authority-term tokens) plus typed follow-needed conjectures
    with route targets when AU events reference authority material that still
    lacks a persisted receipt.
  - AU fact-review bundles now expose that routing metadata in
    `operator_views.authority_follow` with a bounded queue plus route-target
    counts, so authority follow work is visible without inspecting raw
    semantic-context JSON.
  - Extended `scripts/au_fact_review.py` with
    `--no-authority-receipts` and `--authority-receipt-limit`.
  - Extended `src/fact_intake/au_review_bundle.py` so AU review bundles carry
    the new authority-receipt semantic context by default.
  - Added regression coverage in `tests/test_au_semantic.py`,
    `tests/test_au_fact_review_bundle.py`, and
    `tests/test_au_fact_review_script.py`.
- Docs: explicit citation-driven authority follow/ingest user story
  - Added a standalone user story to `docs/user_stories.md` for the
    citation-driven authority flow: cited material -> repo-owned follow seam ->
    bounded authority ingest receipt -> later explicit downstream use.
  - Synced `docs/planning/user_story_implementation_coverage_20260326.md`,
    `todo.md`, and `COMPACTIFIED_CONTEXT.md` so the current boundary is
    explicit: source-pack/HCA/operator lanes can do bounded follow/ingest, but
    ordinary AU semantic runtime still does not auto-follow cite-like text by
    itself.
- Feedback receipt capture ergonomics:
  - Extended `scripts/query_fact_review.py` with `feedback-add` and
    `feedback-import` so bounded `feedback.receipt.v1` rows can be added from
    CLI flags or imported from local JSONL/JSON batches.
  - Added end-to-end coverage for the new capture path in
    `tests/test_query_fact_review_script.py`.
- Docs promotion for AustLII known-authority resolution:
  - Promoted deterministic `MNC -> AustLII case URL` derivation into the
    documented AustLII operator and citation-follow path for known case
    authorities.
  - Updated docs/TODO so AustLII no longer depends on SINO when the neutral
    citation is already known; SINO remains the bounded discovery seam.
  - Added `sensiblaw austlii-case-fetch` so known neutral citations or explicit
    AustLII case URLs can be fetched directly, with local paragraph inspection
    and optional persisted authority-ingest receipts.
  - Added `austlii_case_url_from_mnc(...)` as the promoted deterministic helper
    while retaining `austlii_case_url_guess(...)` as a compatibility alias.
  - Extended `src/ingestion/citation_follow.py` so bounded citation-follow no
    longer stops at JADE: it now falls back to deterministic AustLII case URLs
    when JADE fetch fails or is not preferred, then uses strict AustLII SINO
    exact-citation matching as the final bounded discovery step.
  - Tightened AustLII pacing/timeouts to the documented conservative defaults:
    search now defaults to `0.25 rps` with a longer bounded timeout, and fetch
    now defaults to `0.25 rps`.
  - Added regression coverage in `tests/cli/test_authority_cli.py`,
    `tests/test_citation_follow.py`, and
    `tests/test_citation_normalization.py`.
- Feedback receipt contract + first persisted receiver:
  - Added `database/migrations/014_feedback_receipts.sql` plus canonical
    sqlite storage for bounded `feedback.receipt.v1` rows.
  - Extended `src/fact_intake/read_model.py` and
    `src/fact_intake/__init__.py` with
    `persist_feedback_receipt(...)`,
    `list_feedback_receipts(...)`, and
    `build_feedback_receipt_summary(...)`.
  - Extended `scripts/query_fact_review.py` with `feedback-receipts` and
    `feedback-summary`.
  - Added coverage in `tests/test_query_fact_review_script.py` and
    `tests/test_migration_integrity.py`.
- Docs/state clarification for AU/HCA authority ingest:
  - Clarified repo memory/TODO that broader AU/HCA authority-ingest lanes
    already exist (`source_pack_manifest_pull.py` ->
    `source_pack_authority_follow.py`, `hca_case_demo_ingest.py`), producing
    bounded ingest/timeline/graph artifacts.
  - Clarified the narrower remaining gap: the normal AU semantic/fact-review
    runtime still does not auto-follow AustLII/JADE authorities or reuse the
    persisted authority receipts.
- JADE best-effort search parity + operator cleanup:
  - Added `src/sources/jade_search.py` plus a bounded public `/search/{term}`
    adapter/parser and exact-MNC fallback hit synthesis for operator use.
  - Added `sensiblaw jade-search` with selection, fetch, local paragraph
    inspection, and optional persisted authority-ingest receipts.
  - Moved paragraph-window selection into `src/sources/paragraphs.py` and
    generalized search-hit selection into `src/sources/search_selection.py` so
    JADE no longer depends on AustLII-named helpers for generic behavior.
  - Split mixed coverage into `tests/cli/test_authority_cli.py` and
    `tests/test_jade_live_optin.py`, and added fixture-backed JADE search
    coverage in `tests/test_jade_search.py`.
  - Updated docs and helper scripts so `jade-search` is explicitly secondary
    best-effort, `jade-fetch` remains the stable exact-authority lane, and
    the demo ingest hints use the public `/search/{term}` route.
- Persisted bounded authority-ingest receiver for AU/HCA operator workflows:
  - Added `database/migrations/013_authority_ingest.sql` plus canonical sqlite
    tables for `authority_ingest_runs` and `authority_ingest_segments`.
  - Extended `src/fact_intake/read_model.py` and `src/fact_intake/__init__.py`
    with `persist_authority_ingest_receipt(...)`,
    `list_authority_ingest_runs(...)`, and
    `build_authority_ingest_summary(...)`.
  - Extended `sensiblaw austlii-search` and `sensiblaw jade-fetch` with
    optional `--db-path` persistence so operator-selected authorities can store
    whole-fetch provenance plus bounded paragraph windows without auto-wiring
    authority follow into AU semantic runtime.
  - Extended `scripts/query_fact_review.py` with `authority-runs` and
    `authority-summary`.
  - Added regression coverage in `tests/cli/test_austlii_cli.py`,
    `tests/test_query_fact_review_script.py`, and
    `tests/test_migration_integrity.py`.
- Contested affidavit review persisted receiver:
  - Added `database/migrations/012_contested_affidavit_review.sql` plus
    normalized read-model tables for contested review runs, affidavit rows,
    source-review rows, and persisted Zelph claim-state facts.
  - Extended `src/fact_intake/read_model.py` and `src/fact_intake/__init__.py`
    with `persist_contested_affidavit_review(...)`,
    `list_contested_affidavit_review_runs(...)`, and
    `build_contested_affidavit_review_summary(...)`.
  - Updated `scripts/build_affidavit_coverage_review.py` to accept optional
    `--db-path` persistence while keeping JSON/markdown outputs as derived
    projections.
  - Extended `scripts/query_fact_review.py` with `contested-runs` and
    `contested-summary` for the new persisted receiver.
  - Added regression coverage in `tests/test_affidavit_coverage_review.py`,
    `tests/test_query_fact_review_script.py`, and
    `tests/test_migration_integrity.py`.
- Docs/TODO: clarify bounded authority retrieval workflow:
  - Updated `docs/sources_contract.md` to add the operator workflow for known
    authority retrieval:
    already-ingested/local artifact -> JADE exact MNC when authorized ->
    AustLII SINO search -> explicit AustLII fetch -> local paragraph work.
  - Updated `docs/cli_examples.md` with a concrete `sensiblaw austlii-search`
    example for bounded case lookup/fetch plus local paragraph inspection.
  - Updated `docs/user_stories.md` and root `TODO.md` so the lawyer/case-prep
    lane and remaining gap now explicitly forbid ad hoc site probing outside
    repo-owned source contracts.
- AustLII known-authority local paragraph inspection:
  - Added `src/sources/austlii_paragraphs.py` to index numbered paragraphs
    locally from fetched AustLII HTML artifacts.
  - Extended `sensiblaw austlii-search` with `--paragraph` and
    `--paragraph-window` so known-authority search/fetch can emit local
    paragraph excerpts without a second live retrieval pass.
  - Added fixture-backed coverage in `tests/test_austlii_paragraphs.py` and
    `tests/cli/test_austlii_cli.py`, plus a live opt-in fetch/parse canary in
    `tests/test_austlii_live_optin.py`.
- JADE known-authority local paragraph inspection:
  - Aligned `src/sources/jade.py` with the repo citation contract so neutral
    citations resolve to `content/ext/mnc/...` URLs while explicit JADE URLs
    remain allowed.
  - Added `src/sources/jade_paragraphs.py` to recover numbered paragraphs from
    fetched JADE plain-text or HTML artifacts.
  - Added `sensiblaw jade-fetch` with `--paragraph` and
    `--paragraph-window` so known JADE authorities can be fetched once and then
    inspected locally without a second live retrieval pass.
  - Added fixture-backed coverage in `tests/test_jade_paragraphs.py`,
    `tests/test_jade_adapter_rate_limit.py`, and
    `tests/cli/test_authority_cli.py`, plus an opt-in live JADE fetch/parse
    canary in `tests/test_jade_live_optin.py`.
- JSON artifact boundary + personal-results DB-first correction:
  - Added `docs/planning/json_artifact_boundary_20260327.md` to classify the
    repo's JSON families and make the canonical sqlite/read-model doctrine
    precise.
  - Corrected `itir-svelte /corpora/processed/personal` so persisted `:real_`
    fact-review runs hydrate from the canonical sqlite/workbench path rather
    than checked-in demo-bundle JSON.
  - Kept affidavit review explicit as an artifact-backed surface until that
    lane has a canonical persisted receiver.
- Transcript / observer / Wikidata parity lift:
  - Extended `src/transcript_semantic/semantic.py` so transcript relation rows
    now emit the same relation-candidate metadata as `GWB/AU`:
    `semantic_candidate`, `semantic_basis`, and canonical tetralemma
    promotion fields, while preserving the lane-local `promotion_status`.
  - Extended `src/ontology/wikidata_hotspot.py` with a separate
    `hotspot_pack.semantic_candidate.v1` contract plus central canonical
    promotion metadata for hotspot packs, without forcing relation semantics
    onto pack-shaped outputs.
  - Tightened `tests/test_transcript_semantic.py`,
    `tests/test_wikidata_hotspot.py`, and
    `docs/planning/no_surface_semantic_mapping_policy_20260326.md` so
    mission-observer overlays are explicitly pinned as operational-state-only,
    not truth-bearing semantic promotion outputs.
- GWB/AU semantic promotion parity:
  - Extended `src/policy/semantic_promotion.py` with a minimal
    `relation.semantic_candidate.v1` contract plus a central tetralemma
    mapper for structural semantic-relation rows.
  - Updated `src/gwb_us_law/semantic.py` so each relation row now emits
    `semantic_candidate`, `semantic_basis`, and central
    `canonical_promotion_status` / `canonical_promotion_basis` /
    `canonical_promotion_reason` fields without breaking the existing
    lane-local `promotion_status`.
  - Tightened `tests/test_gwb_semantic.py`, `tests/test_au_semantic.py`, and
    `tests/policy/test_semantic_promotion.py` so AU inherits the same parity
    metadata via `build_au_semantic_report(...)`.
- Contested runtime-depth refinement:
  - Tightened `scripts/build_affidavit_coverage_review.py` so
    `semantic_candidate.target_component` is derived binding-first rather than
    from naive component-target ordering.
  - Extended `semantic_basis` derivation so structurally grounded component
    bindings plus heuristic justification hints can surface as `mixed` instead
    of collapsing to `heuristic`.
  - Added direct coverage in `tests/test_affidavit_coverage_review.py` for
    target-component priority and `mixed` basis derivation.
- Contested candidate schema + truth-bearing inventory:
  - Added `docs/planning/contested_semantic_candidate_schema_20260327.md` to
    freeze the minimal contested semantic candidate object emitted before
    canonical promotion.
  - Extended `src/policy/semantic_promotion.py` with candidate-schema constants,
    builder/validator helpers, and explicit truth-bearing vs non-truth-bearing
    field inventories.
  - Routed the contested lane to emit `semantic_candidate` rows and tightened
    tests so candidate shape and truth-bearing assignment are pinned in code.
- Central semantic promotion gate:
  - Added `src/policy/semantic_promotion.py` with a first central tetralemma
    promotion gate for contested-claim semantics.
  - Routed the contested lane in
    `scripts/build_affidavit_coverage_review.py` through that gate, adding
    `semantic_basis`, `promotion_status`, `promotion_basis`, and
    `promotion_reason` to contested affidavit rows and the flat Zelph bridge.
  - Added direct policy coverage in
    `tests/policy/test_semantic_promotion.py` and tightened the contested
    surface-policy guard to assert that canonical promotion uses the central
    policy gate.
- Contested-lane no-surface-semantic policy and guard:
  - Added
    `docs/planning/no_surface_semantic_mapping_policy_20260326.md` to record
    the rule that semantic labels in this lane must be structural-first and may
    not be derived directly from surface tokens.
  - Added `tests/test_contested_surface_semantic_policy.py` to pin the current
    enforcement boundary: lexical heuristics are quarantined to justification
    hints only, and they do not drive `speech_act`, claim `actor`, or
    claim-state axes.
  - Tightened `scripts/build_affidavit_coverage_review.py` so lexical
    speech-act and actor mappings are removed; only auxiliary lexical
    justification hints remain, under an explicitly named heuristic surface.
- Contested-lane optional structural parser seam:
  - Added an optional dependency-parser path in
    `scripts/build_affidavit_coverage_review.py` that can derive bounded
    subject/negation/hedge signals from the existing repo-local dependency
    helper when spaCy + a dependency model are available.
  - Kept the explicit local rule registry as the fallback so the lane remains
    deterministic in environments where spaCy is declared but not installed.
  - Added test coverage for the structural negated-hedge path via monkeypatch.
- Contested-lane rule substrate cleanup:
  - Replaced the remaining inline contested response heuristics in
    `scripts/build_affidavit_coverage_review.py` with a single local
    rule-registry + evaluator path for `speech_act`, `justification`, and
    `actor` rules.
  - Tightened characterization extraction to boundary-aware regex matches so
    spans are collected explicitly instead of via first-hit substring search.
  - Documented the contested lane’s explicit rule substrate in
    `docs/planning/contested_narrative_response_packet_contract_20260326.md`.
- Contested-narrative response packet compression:
  - Compressed `response.speech_act` in
    `scripts/build_affidavit_coverage_review.py` to a small fixed basis
    (`deny`, `admit`, `explain`, `other`) and moved nuance into
    `response.modifiers`.
  - Extended the flat Zelph bridge with `response_modifiers` so downstream
    consumers can recover hedging, repetition, qualification, and
    non-responsiveness without exploding the enum surface.
  - Updated tests and the contested packet contract note to pin the compressed
    response-act basis plus additive modifiers.
- Contested-narrative response-act refinement:
  - Tightened `scripts/build_affidavit_coverage_review.py` so hedged phrases
    like `I do not feel...` are no longer treated as admissions, and low-overlap
    explanation cues can now downgrade to `non_response` instead of being
    over-promoted as substantive context.
  - Added coverage in `tests/test_affidavit_coverage_review.py` for
    `hedged_denial` and `non_response` classification.
  - Updated the contested packet contract note to document the additive
    `hedged_denial`, `non_response`, and `hedged_denial_signal` surfaces.
- Contested-narrative component packet extension:
  - Extended `scripts/build_affidavit_coverage_review.py` so contested claim
    packets now carry conservative component spans from existing structure:
    optional claim time spans, optional characterization spans, response
    component bindings/targets, and bound justification metadata.
  - Extended the flat `zelph_claim_state_facts` rows with additive component
    fields (`claim_time_spans`, `claim_characterization_spans`,
    `response_component_targets`, `justification_bindings`) without changing
    the existing claim-state axes.
  - Tightened
    `tests/test_google_docs_contested_narrative_review.py` to pin the new
    component-level fields and updated the contested packet contract note to
    document the additive component layer.
- Contested-narrative claim-state/Zelph bridge cleanup:
  - Removed the stale duplicate claim-state bridge helpers from
    `scripts/build_affidavit_coverage_review.py` so the flat
    `zelph_claim_state_facts` rows are the only live downstream contract.
  - Tightened `tests/test_google_docs_contested_narrative_review.py` to pin the
    flat fact shape (`best_source_row_id`, speech-act/polarity fields, and
    justification types) instead of only checking `fact_kind`.
  - Expanded
    `docs/planning/contested_narrative_response_packet_contract_20260326.md`
    with an explicit `Zelph Bridge` section describing the frozen flat bridge
    contract and its boundary relative to nested SensibLaw row packets.
- First anonymous Google public-source adapters:
  - Added `src/fact_intake/google_public_import.py`,
    `scripts/build_personal_handoff_from_google_public.py`, and
    `tests/test_google_public_import.py` to accept public Google Docs/Sheets
    links anonymously and normalize them into the existing handoff/envelope
    contracts.
  - Added `scripts/build_google_docs_contested_narrative_review.py` and
    `tests/test_google_docs_contested_narrative_review.py` to compare a public
    Google affidavit-style document against a public Google response document
    through the existing affidavit-coverage review surface.
  - Extended `scripts/build_affidavit_coverage_review.py` so plain
    `fact.intake.bundle.v1` payloads can be used as source surfaces in this
    review lane.
  - Updated the implementation-coverage audit and TODO wording so the new
    Google public-source seams are reflected in the current honest claim
    boundary.
- Added deterministic lexical-noise actor guards in `src/obligations.py` so
  stopword-only, number-heavy, and citation-only preambles do not create false
  actor anchors before `must/shall/may` modalities.
- Added fixtures and detection coverage under
  `tests/fixtures/actors/` and `tests/test_obligations_detection.py` so
  `A7` lexical-noise fixtures in
  `docs/planning/assumption_controls_registry.json` are now implemented.
- Stronger protected-disclosure envelope semantics:
  - Extended `src/fact_intake/protected_disclosure_envelope.py` with
    disclosure-route gating, identity-minimization modes, and per-item
    retaliation-risk tags while keeping the envelope metadata-only.
  - Added fixture-backed coverage in
    `tests/test_protected_disclosure_envelope.py` for route mismatch and
    identity-minimization exclusions.
  - Updated the implementation-coverage audit and TODO wording so the
    remaining protected-disclosure gap is now live intake/workflow depth, not
    the absence of any retaliation-aware control layer.
- First direct Messenger/Facebook export-backed ingest adapter:
  - Added `scripts/build_personal_handoff_from_messenger_export.py`,
    `src/fact_intake/messenger_export_import.py`, and
    `tests/test_personal_messenger_export_import.py` to feed the personal
    handoff and metadata-only protected-disclosure envelope lanes directly from
    bounded `message_1.json`-style Messenger export inputs.
  - The new adapter filters obvious system/noise rows, preserves the current
    privacy boundary, and reuses the same handoff/envelope contracts instead of
    routing through a sample DB.
  - Updated the implementation-coverage audit, contract note, and TODO wording
    so the remaining ingest gap is now broader multi-source live/export-backed
    coverage rather than the absence of any direct export-backed Messenger
    seam.
- First real export-backed ingest seam:
  - Added `scripts/build_personal_handoff_from_openrecall.py` plus
    `tests/test_personal_openrecall_import.py` to feed the personal handoff and
    metadata-only protected-disclosure envelope lanes from imported
    `openrecall_capture` units.
  - This reuses the existing ITIR/OpenRecall bridge instead of introducing
    another parser or ad hoc import contract, so the private-user lane now has
    one real export-backed source in addition to the bounded JSON and
    sample-DB adapters.
  - Updated the implementation-coverage audit and TODO wording so the
    remaining ingest gap is now broader multi-source live/export-backed
    coverage rather than the absence of any real export-backed seam.
- First repo-local DB-backed ingest seam:
  - Added `scripts/build_personal_handoff_from_message_db.py` plus
    `tests/test_personal_message_db_import.py` to feed the personal handoff and
    metadata-only protected-disclosure envelope lanes directly from
    `chat_test_db` and `messenger_test_db` sample databases.
  - Reused the existing `load_chat_units` / `load_messenger_units` loaders so
    this step extends the ingest surface without introducing another parser or
    contract family.
  - Updated the implementation-coverage audit and TODO wording so the remaining
    ingest gap is now clearly the broader live/export-backed path, not the
    absence of any DB-backed seam.
- First bounded chat/day ingest adapter:
  - Added `src/fact_intake/personal_chat_import.py` and
    `scripts/build_personal_handoff_from_chat_json.py` to normalize bounded
    chat/day JSON into either the full-text personal handoff report or the
    metadata-only protected-disclosure envelope.
  - Added fixtures and coverage in `tests/test_personal_chat_import.py` so the
    repo now has a tested import seam instead of requiring hand-authored entry
    rows for these lanes.
  - Updated the implementation-coverage audit and TODO wording so the docs now
    distinguish the current bounded chat/day adapter from the still-missing
    richer live/import-backed ingest path.
- First metadata-only protected-disclosure envelope:
  - Added `src/fact_intake/protected_disclosure_envelope.py` and
    `scripts/build_protected_disclosure_envelope.py` to implement a separate
    protected-disclosure artifact that does not persist or rehydrate the
    `fact_intake` read-model surfaces.
  - Added fixture-backed coverage in
    `tests/test_protected_disclosure_envelope.py` plus
    `tests/fixtures/fact_intake/protected_disclosure_input_v1.json` to assert
    deny-by-default scoping, scope-mismatch exclusions, and non-leakage of raw
    entry/review/observation text.
  - Updated the planning note, implementation-coverage audit, and TODO wording
    so the repo now distinguishes the full-text personal handoff report from
    the safer metadata-only protected-disclosure envelope.
- First bounded personal handoff implementation:
  - Added `src/fact_intake/personal_handoff_bundle.py` and
    `scripts/build_personal_handoff_bundle.py` to implement the first
    CLI/artifact-first private day-to-escalation lane over the existing
    `fact_intake` substrate.
  - The new path supports recipient-scoped lawyer/doctor/advocate/regulator
    exports, explicit exclusions, text redaction markers, and local-only /
    do-not-sync metadata while preserving fact/review/operator-view outputs.
  - Added fixture-backed coverage in `tests/test_personal_handoff_bundle.py`
    plus a bounded input fixture under `tests/fixtures/fact_intake/`.
  - Updated the planning note, implementation-coverage audit, and TODO wording
    so docs now reflect that the first bounded contract is implemented rather
    than merely planned.
- Wikimedia prior-work and originality note:
  - Added `docs/planning/wikimedia_prior_work_and_originality_note_20260326.md`
    to govern how the Wikimedia grant/demo lane should describe prior work,
    novelty, method overlap, and forbidden wording.
  - The note explicitly separates:
    - Rosario/IBM benchmark framing
    - Ege Doğan / Peter Patel-Schneider disjointness method context
    - Shixiong Zhao / Hideaki Takeda hierarchy-inconsistency context
    - bounded repo-original contribution claims
  - Updated the grant framing note, Rapid Fund draft, bounded demo spec,
    attribution matrix, `COMPACTIFIED_CONTEXT.md`, and `todo.md` so final
    submission wording now has one explicit originality rule surface.
  - No code paths changed; this was a documentation/TODO/changelog alignment
    pass.
- Wikimedia submission-safe re-ranking:
  - Re-ranked the grant demo so the foreground story now rides on the safest
    repo-owned structural packs:
    mixed-order, `P279` SCC, pinned qualifier drift, and bounded disjointness.
  - Demoted the `GNU` / `GNU Project` and finance entity-kind-collapse cases to
    attributed secondary appendix examples rather than lead evidence.
  - Locked the foreground demo inputs to exact fixture/revision artifacts in
    `docs/planning/wikimedia_bounded_demo_spec_20260326.md`.
  - Chose and documented a reviewer route:
    preferred `1-2` Wikidata/ontology-adjacent reviewers, fallback `1-2`
    technically adjacent reviewers.
  - Updated the Rapid Fund draft, framing note, `COMPACTIFIED_CONTEXT.md`, and
    `todo.md` so the remaining grant work is now mostly confirmation/final-entry
    work rather than proposal-structure work.
  - No code paths changed; this was a documentation/TODO/changelog alignment
    pass.
- User-story implementation coverage audit:
  - Added
    `docs/planning/user_story_implementation_coverage_20260326.md` to record
    which story families already have repo-backed code/fixtures/tests and
    which remain aspirational or only partially covered.
  - Updated `docs/user_stories.md` so it explicitly points readers to the
    implementation-coverage note rather than implying all stories are already
    implemented.
  - Added TODOs for the main unimplemented lanes surfaced by the audit:
    private day-to-escalation tooling, whistleblower-safe envelopes,
    provenance-only integrator contracts, community/disability intake,
    annotation/QA workbench, field inspection offline capture, and
    research/publication adapters.
  - Updated `COMPACTIFIED_CONTEXT.md` to preserve the honest claim boundary.
  - No code paths changed; this was a docs/TODO/changelog alignment pass.
- Wikimedia attribution matrix:
  - Added `docs/planning/wikimedia_demo_attribution_matrix_20260326.md` to
    separate case/example lineage from repo contribution for the Wikimedia
    grant/demo lane.
  - The matrix records the safest current reading that the clearest GNU-adjacent
    case in the same hotspot/page-review wave is
    `finance_entity_kind_collapse_pack_v0`, and that both should be treated
    cautiously as attributed examples rather than as repo-original discoveries
    unless stronger provenance later says otherwise.
  - Updated the grant framing note, bounded demo spec, Rapid Fund draft,
    `COMPACTIFIED_CONTEXT.md`, and `todo.md` so attribution guidance now points
    to one explicit repo-local matrix.
  - No code paths changed; this was a documentation/TODO/changelog alignment
    pass.
- Public-servant and community-advocacy crossover expansion:
  - Extended `docs/user_stories.md` with explicit stories for public servants
    witnessing suspected wrongdoing, disability/advocacy organizations, private
    individuals handing off to community/disability supports, private workers
    moving toward integrity processes, and community organizations translating
    bounded evidence to lawyers/regulators/media.
  - This fills a real gap left by the earlier generic government and NGO
    stories: protected disclosure, advocacy intake, and institutional handoff
    are now first-class boundary-sensitive use cases.
  - No code paths changed; this was a docs-only expansion.
- Additional crossovers and single-journey stories:
  - Added to `docs/user_stories.md` a personal day→escalation journey, data
    labeling/annotation team stories, education/research capture→publication,
    SDK/API integrator provenance-only use, and field safety/inspection
    offline-first use.
  - These tighten coverage for partial-stack adopters (provenance-only, offline
    capture) and review-heavy teams (labeling/QA) while preserving the same
    provenance/abstention doctrine.
  - No code paths changed; docs-only.
- Private ↔ institutional crossover user stories:
  - Extended `docs/user_stories.md` with crossover stories for selective
    handoff from private users to lawyers/advocates, care teams,
    journalists/watchdogs, regulators/ombuds, insurers/claims handlers,
    employers/HR/unions, trusted circles, and institutional counterparties.
  - This closes the main gap between the private-user map and the existing
    institutional/professional personas by making boundary-preserving export
    and translation explicit.
  - No code paths changed; this was a docs-only expansion.
- Wikimedia attribution hardening:
  - Tightened the grant/demo surfaces so the `GNU` / `GNU Project` example is
    treated as an attributed reviewed case rather than a repo-original
    discovery.
  - Tightened the disjointness wording so the broader `P2738` method/problem
    context is explicitly credited to Ege Doğan and Peter Patel-Schneider,
    while repo claims stay on the narrower fixture-backed implementation and
    review surfaces.
  - Updated `COMPACTIFIED_CONTEXT.md` and `todo.md` so attribution discipline is
    now a first-class pre-submission requirement for the Wikimedia proposal
    lane.
  - No code paths changed; this was a documentation/TODO/changelog alignment
    pass.
- Personal/private user-story expansion:
  - Extended `docs/user_stories.md` with a `Personal/private client map`
    covering personal capture, timeline/reconstruction, bounded
    obligations/reference, reporting/export, provenance/receipts, local-first,
    and private-to-professional boundary use.
  - Updated `COMPACTIFIED_CONTEXT.md` to make the associated documentation rule
    explicit: private users are first-class, but repo-facing examples stay
    generalized and should not be collapsed into institutional-style
    compliance/reporting language.
  - Added a TODO to keep future packaging and UX notes explicit about the
    difference between private-user surfaces and institutional reporting
    surfaces.
  - No code paths changed; this was a docs/TODO/changelog alignment pass.
- Partial-stack client map:
  - Added a new `Partial-stack client map` section to
    `docs/user_stories.md` so the docs now cover who might use capture,
    timeline/reconstruction, obligations/reference, review-queue, reporting,
    provenance, or local-first layers independently.
  - This makes the commercial/user-story surface less suite-bound and more
    realistic about single-layer adoption paths.
  - No code paths changed; this was a docs-only packaging and positioning
    refinement.
- Delivery / assurance user-story expansion:
  - Extended `docs/user_stories.md` with the missing operational personas that
    sit between product fit and deployment reality: sales/BD, customer
    success/implementation, data/integration engineering, external counsel, and
    regulator/auditor as primary users.
  - The added stories keep the same doctrine as the rest of the file: explicit
    statuses, visible absences, no silent promotion, and no conversion of
    bounded review surfaces into hidden authority.
  - No code paths changed; this was a documentation coverage expansion.
- Aptos thread user-story extraction:
  - Expanded `docs/user_stories.md` with the thread-backed operator stories that
    were implicit in the `Aptos cryptocurrency overview` discussion.
  - Added crypto founder/product, crypto diligence analyst, compliance/regtech
    analyst, exchange/wallet risk operator, real-time alert reviewer,
    institutional buyer/integration lead, Mirror-like partner platform, NGO
    campaign coordinator, and community legal/casework stories.
  - Added a second synthesis pass for institutional-token/compliance use cases:
    institutional investor, token classification analyst, regulatory
    applicability mapper, market stress/bad-day reviewer, and executive/client
    report consumer.
  - The new stories keep the existing doctrine intact: explicit status, visible
    absences, no silent promotion, and no black-box escalation from candidate
    pattern to accepted truth.
  - No code paths changed; this was a documentation extraction pass from the
    archived thread.
- Mirror / Glasslane positioning context refresh:
  - Re-read the archived `Aptos cryptocurrency overview` thread from the local
    chat DB and tightened the repo context/TODO wording around the existing
    Mirror packaging slice.
  - Added the thread-backed market/stage read that Mirror / Glasslane currently
    presents as tiny, founder-led, pre-PMF, and Discord/chatbot-first, with a
    visible audience mix that is looser than the stated professional target.
  - Recorded the thread's NFT/token monetization discussion as part of the
    packaging context so future drafts keep the provenance/governance layer
    differentiation explicit.
  - No code paths changed; this was a docs/TODO/changelog alignment pass.
- Cross-lane normalized review metrics:
  - Added `scripts/review_geometry_normalization.py` and threaded
    `normalized_metrics_v1` into the AU affidavit coverage review, checked/dense
    Wikidata structural review, and checked/broader GWB review artifacts.
  - Added
    `tests/fixtures/zelph/review_geometry_normalized_summary_v1/review_geometry_normalized_summary_v1.{json,summary.md}`
    as the first generated cross-lane comparison surface over AU, Wikidata,
    and GWB review checkpoints.
  - The new normalized layer is additive: existing lane-local counts and
    ranking scores remain intact, while comparable status/workload/density
    metrics now sit beside them.
  - Added fixture-backed tests for the normalized metric layer and the new
    comparison artifact.
- Wikimedia bounded-demo collapse:
  - Added `docs/planning/wikimedia_bounded_demo_spec_20260326.md` to choose the
    concrete grant-demo subset, target properties, review-class definitions,
    and evaluation baseline from existing repo-backed Wikidata artifacts.
  - The chosen proposal story is now a hybrid of:
    - article-backed entity-kind review on `GNU` / `GNU Project`
      (`Q44571` / `Q7598`) for `P31` / `P279` / `P527`
    - pinned structural validation on `Q100104196|P166`,
      `Q100152461|P54`, `fixed_construction_contradiction`, and
      `working_fluid_contradiction`
  - Updated the Rapid Fund draft so it now cites the exact bounded demo scope,
    uses manual bounded review plus the current repo checked-review process as
    its baseline, and names concrete reviewer-facing pain points instead of
    generic Wikidata quality language.
  - Added a Wikimedia/Wikidata contributor user story to
    `docs/user_stories.md` so the grant story stays governed by the same
    provenance/no-silent-promotion doctrine as the rest of the repo.
  - Updated `README.md`, `docs/wikidata_working_group_status.md`,
    `COMPACTIFIED_CONTEXT.md`, and `todo.md` to reflect that demo-scope and
    baseline selection are now done at the draft level.
  - No code paths changed; this was a documentation/TODO/changelog alignment
    pass.
- Wikimedia submission-hardening pass:
  - Upgraded `docs/planning/wikimedia_rapid_fund_draft_20260326.md` from a
    generic Rapid Fund draft into a Wikimedia-style application artifact with
    explicit project-summary/problem/solution/support/users/activities/outputs
    fields.
  - Added reviewer-facing evaluation metrics, acceptance criteria, evaluation
    plan, and a short risk/mitigation section so the draft is closer to
    submission-ready and less dependent on ad hoc later rewriting.
  - Updated the framing note, `README.md`, `COMPACTIFIED_CONTEXT.md`, and
    `todo.md` so the repo now treats evaluation-metric design as done at the
    draft level and the next steps as subset/baseline selection plus exact
    submission-field translation.
  - No code paths changed; this was a documentation/TODO/changelog alignment
    pass.
- Wikimedia proposal draft formalization:
  - Added `docs/planning/wikimedia_rapid_fund_draft_20260326.md` as the first
    concrete repo-local Rapid Fund-ready draft for the bounded Wikidata lane.
  - The draft includes a full proposal skeleton plus a ZKP
    (`O,R,C,S,L,P,G,F`) formalization so the external Wikimedia-facing pitch
    and the internal system model stay aligned.
  - Updated the grant framing note, `README.md`,
    `docs/wikidata_working_group_status.md`, `COMPACTIFIED_CONTEXT.md`, and
    `todo.md` so the repo now points to one explicit draft artifact and treats
    Meta/Fluxx field translation plus evaluation metrics as the next proposal
    step.
  - No code paths changed; this was a documentation/TODO/changelog alignment
    pass.
- Wikimedia grant framing alignment:
  - Added `docs/planning/wikimedia_grant_framing_20260326.md` to separate
    external Wikimedia funding/program framing from the repo's internal
    Wikidata review-surface status.
  - Documented the current outward-facing recommendation as a bounded
    provenance-aware Wikidata validation/ingestion tool, with Rapid Fund as the
    first practical proposal shape and Research Fund as the more
    methodology-heavy alternative.
  - Updated `README.md`, `docs/wikidata_working_group_status.md`,
    `COMPACTIFIED_CONTEXT.md`, and `todo.md` so funding/proposal discussion now
    points at one explicit note instead of being implied through the internal
    status docs.
  - No code paths changed; this was a docs/TODO/changelog consistency update.
- Cross-lane review-geometry parity documentation:
  - Added `../docs/planning/review_geometry_parity_20260326.md` to capture the
    current operator-facing review geometry across AU, Wikidata, and GWB,
    including a plain-language reading of the new checked/dense Wikidata review
    artifacts and the checked/broader GWB review artifacts.
  - Updated `docs/wikidata_working_group_status.md`, `COMPACTIFIED_CONTEXT.md`,
    and `todo.md` so the repo now records the active Wikidata review surfaces
    explicitly and treats normalized cross-lane workload/ranking metrics as the
    next step rather than jumping straight to shared-core extraction.
  - Clarified after an online funding check that external Wikimedia grant state
    is separate from the repo's internal review-surface status: current docs no
    longer imply there is one simple repo-local list of "active Wikidata
    grants", and instead distinguish open movement funding paths from active
    diagnostics/review surfaces.
- Wikidata structural review parity:
  - Added `scripts/build_wikidata_structural_review.py` plus
    `tests/test_wikidata_structural_review.py` and generated
    `tests/fixtures/zelph/wikidata_structural_review_v1/`.
  - Added `scripts/build_wikidata_dense_structural_review.py` plus
    `tests/test_wikidata_dense_structural_review.py` and generated
    `tests/fixtures/zelph/wikidata_dense_structural_review_v1/`.
  - The checked review turns the bounded handoff into a compact queue of named
    structural disputes and governance-held hotspot review, while the dense
    review expands that same queue into a larger raw structural evidence
    surface.
- GWB review parity:
  - Added `scripts/build_gwb_public_review.py` plus
    `tests/test_gwb_public_review.py` and generated
    `tests/fixtures/zelph/gwb_public_review_v1/`.
  - Added `scripts/build_gwb_broader_review.py` plus
    `tests/test_gwb_broader_review.py` and generated
    `tests/fixtures/zelph/gwb_broader_review_v1/`.
  - The checked GWB review now makes topical bleed and linkage pressure visible
    as row-level review work, while the broader review surfaces cross-family
    workload pressure above the existing broader corpus checkpoint.
- Checked AU dense affidavit-coverage artifact:
  - Added `scripts/build_au_dense_affidavit_coverage_review.py` plus
    `tests/test_au_dense_affidavit_coverage_review.py` and the checked fixture
    directory `tests/fixtures/zelph/au_dense_affidavit_coverage_review_v1/`.
  - The first dense AU artifact compares an affidavit-style draft against the
    24-row dense overlay projection from
    `au_real_transcript_dense_substrate_v1`, making corpus-side omission review
    pressure visible beyond the 3-fact AU checked handoff slice.
  - Current checked dense reading is conservative but useful:
    `2` partial propositions, `1` unsupported affidavit proposition, and `22`
    missing-review source rows.
- Checked AU affidavit-coverage artifact:
  - Added `scripts/build_au_affidavit_coverage_review.py` plus
    `tests/test_au_affidavit_coverage_review.py` and the checked fixture
    directory `tests/fixtures/zelph/au_affidavit_coverage_review_v1/`.
  - The first AU-specific artifact compares the checked `au_public_handoff_v1`
    slice against a bounded affidavit-style draft and emits explicit
    coverage statuses under the shared affidavit-review contract.
  - Current checked AU reading is intentionally conservative:
    `1` covered proposition, `2` unsupported affidavit propositions, and `2`
    missing-review source rows.
- First affidavit-coverage review builder:
  - Added `scripts/build_affidavit_coverage_review.py` to build a bounded
    corpus-to-affidavit comparison artifact from an existing
    `fact.review.bundle.v1` payload or AU checked handoff slice plus an
    affidavit/declaration draft.
  - The first contract emits explicit affidavit-side and source-side statuses,
    including `covered`, `partial`, `missing_review`, `contested_source`,
    `abstained_source`, and `unsupported_affidavit`.
  - Added focused regression coverage in
    `tests/test_affidavit_coverage_review.py`.
- Mary/AU affidavit-coverage planning alignment:
  - Added `docs/planning/affidavit_coverage_review_lane_20260325.md` to define
    the first bounded corpus-to-affidavit coverage review lane over the
    existing dense substrate and fact-review surfaces.
  - Added `SL-US-31` to `docs/user_stories.md` so the repo now treats
    corpus-to-affidavit coverage as an explicit legal-operator story rather
    than an implied future use case.
  - Updated the Mary-parity acceptance matrix, status audit, AU completeness
    scorecard, `TODO.md`, and `COMPACTIFIED_CONTEXT.md` so the next AU/Mary
    step is framed as coverage accounting and omission review, not just more
    extraction density.
- Wikidata checked handoff parity:
  - Added `scripts/build_wikidata_structural_handoff.py` plus
    `tests/test_wikidata_structural_handoff.py` and generated
    `tests/fixtures/zelph/wikidata_structural_handoff_v1/` so the wiki/Wikidata
    lane now has a checked summary/JSON/ZLP/scorecard artifact parallel to GWB
    and AU.
  - The new handoff uses the repo-pinned qualifier baseline and live drift
    case as its core, the hotspot pilot manifest as the governance/exemplar
    layer, and the real disjointness packs as the secondary contradiction lane.
  - Updated shared handoff docs and the working-group status note so the new
    artifact is described as a real bounded handoff rather than a docs-first
    target.
- GWB broader-source corpus expansion:
  - Fixed `scripts/build_gwb_public_bios_rich_timeline.py` so malformed HTML
    paragraph transitions no longer drop strong public-bios sentences; explicit
    statute-signing lines like the No Child Left Behind sentence now survive as
    standalone events in `demo/ingest/gwb/public_bios_v1/wiki_timeline_gwb_public_bios_v1_rich.json`.
  - Added a reviewed `gwb_us_law:no_child_left_behind_act` linkage seed and a
    narrow broader-source semantic backfill path so matched public-bios events
    can promote `George W. Bush -> signed -> No Child Left Behind Act` without
    loosening general promotion policy.
  - Added a reviewed
    `gwb_us_law:northwestern_hawaiian_islands_marine_national_monument`
    linkage seed so the explicit public-bios proclamation event promotes
    `George W. Bush -> signed -> Northwestern Hawaiian Islands Marine National Monument`
    through the existing signed/legal-ref path.
  - Replaced the earlier broader-source alias inflation with one canonical NCLB
    legal-ref target, so the broader checkpoint records one real new promoted
    family rather than two title variants.
  - Fixed `scripts/gwb_corpus_timeline_build.py` by importing `re`, filtering
    more TOC/index noise, and prioritizing legally salient sentences across the
    full corpus text instead of mostly front-loading early-book material.
  - That corpus shaping now surfaces real `Decision Points` legal snippets
    (FISA, Harriet Miers, Supreme Court material, military-tribunal passages),
    which lifts the corpus/book lane from a weak broad-cue surface to real
    broader-source nomination/review confirmations and one new merged relation:
    `George W. Bush -> ruled_by -> Supreme Court of the United States`.
  - Tightened generation ambiguity handling so father-era corpus passages with
    explicit global kinship cues like `his son` no longer overresolve `Bush` or
    `George Bush` to `actor:george_w_bush`.
  - Wired the existing corpus-builder `root_actor` memoir hint into a
    conservative first-person legal-action pass in `src/gwb_us_law/semantic.py`
    and expanded the reviewed stem-cell linkage cues so the corpus/book lane
    now independently confirms
    `George W. Bush -> vetoed -> Stem Cell Research Enhancement Act`
    without changing the honest deduped broader-checkpoint total.
  - Updated broader GWB diagnostics/checkpoint artifacts and tests; current
    merged checkpoint now reports `18` distinct promoted relations and `3` new
    distinct promoted relations beyond the checked handoff.
- AU broader-corpus parity:
  - Added `scripts/build_au_broader_corpus_diagnostics.py` plus
    `tests/test_au_broader_corpus_diagnostics.py` and generated
    `tests/fixtures/zelph/au_broader_corpus_diagnostics_v1/` so AU now has a
    broader-corpus companion alongside the scorecard and checked handoff.
  - Added `scripts/build_au_transcript_structural_checkpoint.py` plus
    `tests/test_au_transcript_structural_checkpoint.py` and generated
    `tests/fixtures/zelph/au_real_transcript_structural_checkpoint_v1/` from
    the real HCA hearing transcript files.
  - Upgraded `src/reporting/structure_report.py` so AustLII/HCA hearing text
    splits on speaker turns and Whisper-style timestamp markdown groups into
    sentence-ish transcript units instead of one or two giant blobs.
  - This gives AU an internal real-transcript structural/legal checkpoint while
    staying honest that the generic transcript fact-review path is still too
    noisy to count as reviewed fact/event coverage.
  - Added `scripts/build_au_transcript_dense_substrate.py` plus
    `tests/test_au_transcript_dense_substrate.py` and generated
    `tests/fixtures/zelph/au_real_transcript_dense_substrate_v1/` so the real
    HCA hearing lane now has a dense transcript-derived substrate artifact
    alongside the narrower reviewed handoff.
  - The dense AU artifact currently reports `1747` transcript units,
    `1747` facts, `1482` observations, `0` events, and a 24-row secondary
    review-overlay projection, making transcript density explicit instead of
    treating it as an error to collapse immediately.
  - Added explicit `--reviewed-event-limit` CLI control to tune reviewed hearing
    event projection size from `build_au_transcript_dense_substrate.py` and
    validated a higher-coverage run (`/tmp/au_real_round2_v2`) at
    `--reviewed-event-limit 24`, which yields `183` reviewed-event queue links,
    `24` selected reviewed hearing events, and `0.104751` reviewed-event
    coverage ratio.
  - Added opt-in `--progress` stage reporting to the AU structural-checkpoint
    and dense-substrate builders so longer runs can emit stderr progress events
    without changing default stdout artifact/result behavior.
  - Propagated the same opt-in `--progress` stage reporting contract into
    `scripts/transcript_semantic.py` and `scripts/transcript_fact_review.py`.
  - Extended `persist_fact_intake_payload(...)` to emit nested section progress
    with totals, elapsed seconds, item rates, estimated finish times, and
    heuristic ETA intervals, and threaded those updates through the transcript
    review/dense AU builders.
  - Added shared `scripts/cli_runtime.py` for human-first stderr progress,
    optional terminal bar rendering, optional JSON progress for wrappers, and
    CLI logging configuration, and rolled `--log-level` plus opt-in progress
    rendering through `transcript_semantic.py`, `transcript_fact_review.py`,
    `au_fact_review.py`, `build_au_transcript_structural_checkpoint.py`,
    `build_au_transcript_dense_substrate.py`,
    `build_gwb_public_bios_rich_timeline.py`,
    `gwb_corpus_timeline_build.py`,
    `build_gwb_broader_corpus_checkpoint.py`,
    `build_gwb_broader_promotion_diagnostics.py`,
    `run_wikidata_qualifier_drift_scan.py`, and
    `wiki_revision_pack_runner.py`.
  - Threaded progress into the deeper Wikidata/Wikipedia internals too:
    `src/ontology/wikidata.py::find_qualifier_drift_candidates(...)` now emits
    candidate-query, revision-metadata, and revision-compare updates, while
    `src/wiki_timeline/revision_pack_runner.py::run(...)` now emits per-article,
    history, candidate-scoring, and pair-report progress. Added renderer tests
    in `tests/test_cli_runtime.py`.
  - Extended the dense AU transcript artifact with a first hearing-procedural
    reviewed projection so court interventions, party submissions, and
    statute-heavy turns are surfaced separately from the flatter dense fact
    layer.
  - Extended that AU dense hearing lane again so it now carries a first
    classified `hearing_act` layer and bounded `procedural_move` assembly over
    adjacent compatible hearing turns, making the next bottleneck explicit as
    broader reviewed event assembly rather than transcript density collapse.
  - Extended the same AU hearing lane again with a first conservative
    `event_assembly_overlay` over procedural moves, so the dense transcript
    artifact now reaches bounded hearing-event structure while keeping persisted
    fact-review event counts unchanged and conservative.
  - Extended that AU `event_assembly_overlay` again so it now assembles short
    local bench/counsel exchanges and authority/submission clusters, not only
    single-move hearing events.
  - Added event-assembly coverage metrics over the procedural-move layer so AU
    hearing progress is now measurable as coverage of local procedural
    structure, not just raw event counts.
  - Preserved explicit speaker labels across AU hearing acts, procedural moves,
  and assembled events so local bench/counsel exchange assembly is less
  dependent on topic overlap alone.
  - Tightened the conservative AU event contract so local cue strength,
    speaker continuity, and bounded topic continuity now work together in the
    event assembler instead of topic overlap carrying too much of the load.
  - Preserved transcript-order semantics on AU procedural moves and switched
    event assembly to use hearing order rather than ranked move order, fixing a
    real exchange-chain assembly bug.
  - Normalized AU section references and case-style authority cues into topic
    continuity tokens (for example `section_6k`) so statute/authority carryover
    is stronger across adjacent moves and assembled events.
  - Added a reviewed hearing-event projection above the AU assembled-event
    layer so the dense transcript artifact now exposes a smaller
    operator-facing event review surface derived from assembled local hearing
    events plus linked fact/review support, rather than only a dense fact
    overlay.
- Zelph handoff documentation alignment:
  - Added a canonical Zelph handoff index and clarified the reading order
    between external framing, pack definition, artifact-specific handoff notes,
    and corpus-level completeness notes.
  - Added the broader-companion pack note + manifest:
    `docs/planning/zelph_real_world_pack_v1_6_20260325.md` and
    `docs/planning/zelph_real_world_pack_v1_6.manifest.json`.
  - Recorded the current corpus-expansion priority order:
    broader GWB public-source extraction first, AU transcript/WhisperX-backed
    expansion second, and safe chat-history lane third.
- QG/DA51/Agda boundary contract (documentation capture):
  - Added `docs/plan_qg_unification_sl_da51_agda_contract_20260324.md` to
    record the resolved `QG Unification Proofs` thread outcome as an interface
    contract reference for future cross-project integration.
  - Updated `docs/interfaces.md` to include the proposed boundary semantics and
    the non-authoritative "documentation-only for now" status of this lane.
  - Added a follow-up task entry in `todo.md` to keep the contract in the
    Medium-Term workflow with explicit adapter gating before any implementation
    starts.
  - Added `src/qg_unification.py` as a minimal boundary scaffold that validates
    `DA51Trace`, projects it to `TraceVector`, and emits a typed adapter
    envelope.
  - Added a smoke-run utility at `SensibLaw/scripts/qg_unification_smoke.py` to
    render `TraceVector` + dependency envelope output from a sample payload.
  - Extended smoke utility with `--invalid` mode to emit deterministic validation
    failures for malformed `DA51Trace` payloads.
  - Added a one-command smoke runner:
    `SensibLaw/scripts/run_qg_unification_smoke.sh` (sets `PYTHONPATH=.` so imports resolve).
  - Added deterministic DA51 fixture payloads under
    `SensibLaw/tests/fixtures/qg_unification/` and taught the smoke utility to
    replay them via `--json-file`.
  - Added stage-2 artifact bridge script:
    `SensibLaw/scripts/qg_unification_stage2_bridge.py`, which validates
    `DA51Trace`, emits deterministic `TraceVector` + envelope payloads, and
    persists staged JSON artifacts to a configured output directory.
  - Extended stage-2 bridge to support optional SQLite persistence:
    when `--db-path` is provided, stage outputs are upserted into a durable
    `qg_unification_runs` table in that database for downstream adapter query.
  - Added `SensibLaw/scripts/run_qg_unification_stage2_fixture.sh` and verified
    that the valid fixture writes both an artifact JSON and a durable
    `qg_unification_runs` SQLite row.
- Added Stage-3 read-model adapter:
  `SensibLaw/scripts/qg_unification_to_itir_db.py` to consume staged runs from
  `qg_unification_runs` and persist them deterministically into an ITIR-facing
  `qg_unification_runs` table (`INSERT OR REPLACE`) for downstream consumers.
  - Added Stage-3b TiRC/transcript capture adapter:
    `SensibLaw/scripts/qg_unification_to_tirc_capture_db.py`, which resolves
    bridge-run records and writes deterministic transcript-style capture rows into
    `qg_tirc_capture_runs`, `qg_tirc_capture_sessions`, and
    `qg_tirc_capture_utterances`.
- AU/GWB corpus-level completeness checkpoints:
  - Added `scripts/build_au_corpus_scorecard.py` to aggregate the persisted
    real AU and transcript-adjacent fact-review bundles into one
    machine-readable corpus checkpoint plus a plain-language summary.
  - Added `scripts/build_gwb_corpus_scorecard.py` to inventory the broader
    in-repo GWB source families, including the checked handoff, public-bios
    pack, corpus timeline, and local book/demo files.
  - Added focused tests for both scorecard builders and generated the checked
    artifacts under `tests/fixtures/zelph/au_corpus_scorecard_v1/` and
    `tests/fixtures/zelph/gwb_corpus_scorecard_v1/`.
- Broader GWB extraction checkpoint:
  - Added `scripts/build_gwb_broader_corpus_checkpoint.py` to combine the
    checked handoff lane with fresh deterministic extraction over the
    public-bios and corpus/book timelines.
  - Added `scripts/build_gwb_public_bios_rich_timeline.py` to rebuild the
    public-bios input from raw HTML cue-bearing snippets instead of title-only
    rows, and generated
    `demo/ingest/gwb/public_bios_v1/wiki_timeline_gwb_public_bios_v1_rich.json`.
  - Added a focused test for the richer public-bios timeline builder.
  - Added `scripts/build_gwb_broader_promotion_diagnostics.py` plus a focused
    test and generated
    `tests/fixtures/zelph/gwb_broader_promotion_diagnostics_v1/` to explain
    why broader-source GWB runs widen seed support without widening promoted
    relation coverage.
  - Added a broader-source seed-backed candidate backfill in
    `src/gwb_us_law/semantic.py` so public-bios and corpus/book lanes can
    reach candidate-level semantic anchoring on strong matched-seed events
    without loosening promotion policy or perturbing the checked wiki handoff.
  - Tightened that broader-source seed-backed semantic pass so the repeated
    Supreme Court review family now promotes under policy-evaluated confidence
    when the broader-source text explicitly names the court/decision and the
    subject/object are already resolved.
  - Added generation-aware bare-`Bush` abstention in
    `src/gwb_us_law/semantic.py` plus a regression test so explicit
    father/family-history corpus contexts no longer silently resolve to
    `actor:george_w_bush`.
  - Added a focused test and generated the checkpoint artifact under
    `tests/fixtures/zelph/gwb_broader_corpus_checkpoint_v1/`.
  - Recorded the updated result honestly: richer public-bios input lifted that
    lane from `0` to `1` matched seed lane, but the broader families still add
    `0` new promoted relations beyond the checked handoff; after the new
    broader-source semantic pass, both broader families now yield relation
    candidates, promoted confirmations, and text-debug support on the repeated
    Supreme Court review family, so the next bottleneck is broadening beyond
    that first repeated-family confirmation rather than inventory.
- Wikipedia random article-ingest live campaign follow-up:
  - Recorded the first completed recursive random-run results, including the
    observed gap between root-link relevance (`0.982143`) and followed-link
    relevance (`0.5625`) plus the current follow-target-quality average
    (`0.446047`).
  - Confirmed on the first 8-page live slice that hop-2 quality did not
    collapse relative to hop-1, so shallow path decay is not yet the primary
    graph-yield failure.
  - Tightened the next work focus around list/year/generic aggregation follow
    pages after the weakest follow targets clustered around `non_list_score =
    0.0`.
  - Added archived repeat-run tooling plus a report-aggregation helper so
    operators can run multi-campaign follow-quality sweeps and cluster the weak
    follows without hand-editing temp paths.
  - Tightened `non_list_score` so title-level and warning-level aggregation
    cues now penalize list/disambiguation/year-style follow pages more sharply,
    while the report surfaces explicit follow-failure buckets and examples.
  - Fixed a follow-target-quality false positive where raw wikitext
    `[[Category:...]]` residue could make ordinary pages look list-like; the
    non-list detector now strips category/defaultsort markup before scoring.
  - Recorded the corrected 3-run post-fix aggregate: root-link relevance stayed
    near-saturated, follow-target quality remained materially lower, hop decay
    stayed near zero, and `list_like_follow` still dominated the weak follow
    buckets with `low_information_gain_follow` second.
  - Implemented the first continuation-specificity slice without changing the
    4-part follow-target-quality blend or the existing weak-follow thresholds.
  - Expanded `non_list_score` / `list_like_follow` with bounded title
    heuristics, lexical parent-child specificity checks, and same-
    neighborhood/no-lift detection for generic continuation pages.
  - Added explicit specificity reasons to follow-detail output and aggregate
    summaries so the next 3x8 rerun can show which generic-follow shapes still
    dominate before any `low_information_gain_follow` tuning.
  - Locked the next phase around fixed-manifest rescoring/report comparison and
    a follow-on refinement inside the existing information-gain component for
    related-but-generic continuations.
  - Added fixed-manifest rescoring/report comparison support so scorer changes
    can now be measured on the same manifests instead of only against fresh
    random samples.
  - Tightened the existing information-gain component for related-but-generic
    continuations using bounded penalties for year/umbrella/generalization and
    low-novelty signals, while keeping the overall follow-target-quality score
    shape unchanged.
  - Recorded the fixed-manifest comparison result for that slice: the new
    information-gain instrumentation was useful, but the score penalties were
    too broad, leaving `list_like_follow` unchanged on the same manifests,
    nudging `low_information_gain_follow` only slightly upward, lowering
    average `follow_target_quality_score`, and leaving hop decay effectively
    flat.
  - Added a cross-bucket diagnostic guard so mixed follow failures prefer
    `low_information_gain_follow` unless an explicit bucket override is present;
    this keeps generic low-lift aggregations grouped with information-gain
    failures for cleaner residual clustering.
  - Narrowed those information-gain penalties so title-shape cues now need
    co-occurring low-novelty / no-lift evidence before they become the main
    score penalty, and confirmed on the same manifests that the scorer stayed
    effectively neutral while preserving the reason instrumentation.
- Wikipedia random article-ingest generalization harness:
  - Extended the random-page ingest report with dominant-regime counts and
    follow-yield summary metrics so larger manifest runs can falsify the regime
    basis, not just confirm that a handful of pages score cleanly.
  - Kept page-family labels as derived debug output while surfacing
    regime-generalization and graph-yield summaries at the report level.
  - Tightened follow-target quality to the explicit richness / non-list /
    regime-similarity / information-gain blend, and made follow-yield a
    50/50 blend of followed-link relevance and continuation quality.
  - Added hop-1/hop-2 decay and best-path probing so the graph-yield surface
    now distinguishes useful continuation nodes from merely relevant link
    overlap.
  - Ran a recursive live sample and confirmed the new summary fields stay
    coherent on follow-linked pages, including cases where follow-target
    quality decays modestly over two hops.
- Follow-quality continuation specificity hardening (Slice 1/Slice 2 v0.11->v0.12):
  - Added parent-child generalization and generic-umbrella specificity signals into
    continuation profiling, including `parent_child_generalization` and
    `parent_child_no_lift` markers.
  - Made parent-child/general-title continuations more likely to surface as
    weak continuations when lift is low, without changing the follow-target blend.
  - Added additional low-information gain penalties tied to low novelty + same-
    neighborhood + parent-child generalization, while requiring novelty/no-lift
    evidence before title-shape alone can drive the penalty.
  - Hardened report scoring against malformed cached follow snapshots by normalizing
    structured/non-string `wikitext` payloads before sentence extraction and
    returning bounded `snapshot_missing_wikitext` rows when empty.
- Wikipedia random article-ingest regime basis:
  - Added a small regime vector to the canonical article state so ingest
    scoring can distinguish narrative, descriptive, and formal pages without
    exploding the page-family taxonomy.
  - Added regime-aware honesty/calibration score paths to the random-page
    article-ingest report while keeping the legacy score family for
    compatibility and comparison.
  - Re-ran the stored random-page manifest and confirmed the regime split is
    sensible on biography/place/facility/project/species samples.
- Wikipedia random article-ingest consistency follow-up:
  - Recorded the first stored-manifest calibration findings in local context and
    tightened the report/docs around what the new calibration layer is actually
    showing.
  - Clarified that link relevance currently measures sentence-local
    actor/object/attribution participation and still needs a stronger
    centrality/follow-yield formulation before it becomes a useful discriminator.
  - Tightened the family classifier so biography pages no longer misclassify as
    taxonomy pages, and kept family-aware summary reporting aligned with the
    current report semantics.
  - Corrected the local context note around the referenced ChatGPT UUID so a
    later `re_gpt` auth failure is not misread as proof that the original pull
    or earlier context ingestion failed.
- Wikipedia random article-ingest calibration pass:
  - Added a third scorer-only calibration layer over the random-page report for
    abstention quality, sentence-link relevance, and claim/attribution
    grounding, keeping the earlier coverage and honesty tracks intact.
  - Added heuristic page-family profiling and summary stratification so random
    biography/place/facility/project/species pages can be compared without
    collapsing into one blended average.
- Wikipedia random article-ingest scoring honesty pass:
  - Kept the earlier coverage-oriented article-ingest scores for report
    continuity, but added a second honesty-oriented score family so noisy
    extraction no longer looks near-perfect by default.
  - Added scorer-only penalties for observation explosion, malformed extracted
    text, weak actor-action binding, and weak object binding, plus page-level
    density metrics for observations/events/steps.
  - Added separate timeline-honesty reporting over explicit/weak/none anchor
    ratios so chronology quality is visible without treating mostly undated
    pages as article-ingest failures.
- Fact semantic benchmark hardening:
  - Added prompt-injection/link-spam/code-switch/redaction adversarial entries across wiki, chat, transcript, and AU legal corpora.
  - Added corpus shape/adversarial smoke test (`tests/test_fact_semantic_bench_corpora.py`).
  - Re-ran matrix benchmarks at tiers 100 and 1000 for all corpora; refresh status remains OK.
  - Extended the benchmark scripts with per-entry diagnostics, expected-vs-realized class/policy recall, baseline drift comparison, and guardrail/review summaries so wiki and AU legal drift can be inspected without manual report diffing.
- Mary-parity fact-intake scaffold:
  - Added a first SQLite read-model migration for canonical
    `source -> excerpt -> statement -> fact candidate -> contestation/review`
    storage in `fact_intake_*` tables.
  - Added the SL-native `src/fact_intake` package surface, deterministic
    `TextUnit` sender helper, canonical persistence/report functions, and a
    Mary-compatible `mary.fact_workflow.v1` projection facade over the same
    read models.
  - Added a checked-in contract doc, schema, minimal example bundle, and
    focused tests covering schema validation, deterministic payload building,
    provenance drill-down, chronology ordering, contestation/review visibility,
    and replace-on-repersist behavior for a run.
  - Added the first deterministic `ObservationRecord -> EventCandidate`
    assembler with canonical `event_candidates`, `event_attributes`, and
    `event_evidence` tables, conservative signature-based event merging, and
    report/projection visibility for derived event rows while keeping
    observations canonical.
  - Tightened the fact/event substrate contract with explicit status vocab,
    abstention-preserving behavior, and validation guards so unsupported
    statement/observation/fact statuses fail closed while abstained
    observations remain stored but do not silently drive event assembly.
  - Added a transcript-first Mary-parity adapter from `transcript_semantic`
    into the fact-intake substrate plus a dedicated
    `fact.review.bundle.v1` operator payload, schema/example contract, and
    focused end-to-end tests covering transcript observation mapping,
    derived communication events, chronology/review-bundle projection, and
    semantic provenance carried through to derived event rows.
  - Added `scripts/transcript_fact_review.py` as a thin operator entrypoint
    for transcript-backed fact review runs and bundle emission, with focused
    script tests covering both summary and full-bundle output over file-based
    transcript fixtures.
  - Added the matching AU-semantic parity lane with
    `src/fact_intake/au_review_bundle.py`,
    `scripts/au_fact_review.py`, and focused tests proving that AU semantic
    reports can be projected into the same `fact.review.bundle.v1` contract
    with legal-domain observations, derived events, chronology, and operator
    bundle output.
  - Tightened the Wave 1 legal parity gate for transcript/non-AU runs by
    preserving explicit observation-level `signal_classes`, carrying explicit
    source provenance signal classes through the workbench for every fact,
    broadening legal/procedural visibility from structured observation/source
    metadata instead of string heuristics, and splitting workbench display into
    observation signals vs source provenance. The canonical `wave1_legal`
    five-fixture acceptance batch now passes `SL-US-09` through `SL-US-14`
    cleanly.
  - Extended the acceptance harness to support per-wave fixture manifests and
    added a canonical `wave2_balanced` gate with balanced real/synthetic
    fixtures for `ITIR-US-11` and `ITIR-US-12`, including dedicated personal
    fragments and investigative reopen fixtures. The batch runner now supports
    `wave2_balanced`, and the canonical Wave 2 set passes cleanly.
  - Added Wave 3 trauma/advocacy hardening and the parallel contested
    wiki/Wikidata/public-figure acceptance track. The acceptance harness now
    includes explicit `ITIR-US-13/14` hardening checks plus first-class
    `SL-US-15` through `SL-US-24` public-knowledge story gates, new trauma and
    public-knowledge fixture manifests/builders, and additive operator views
    for trauma handoff, public claim review, wiki fidelity, and claim
    alignment. The canonical `wave3_trauma_advocacy` and
    `wave3_public_knowledge` fixture sets both pass cleanly.
  - Extended the same acceptance-first parity pattern into bounded Wave 4
    family-law / cross-side and medical / professional-discipline fixture
    families. The harness now includes `SL-US-25` through `SL-US-30`,
    dedicated Wave 4 manifests/builders, and runner/test support for
    `wave4_family_law` and `wave4_medical_regulatory`.
  - Added a bounded Wave 5 ITIR acceptance lane for personal-to-professional
    provenance handoff and anti-false-coherence / anti-AI-psychosis pressure.
    The harness now includes `ITIR-US-15` and `ITIR-US-16`, a dedicated Wave 5
    manifest/builders, runner/test support for
    `wave5_handoff_false_coherence`, and additive read-only workbench views for
    professional handoff and false-coherence review.
  - Broadened Wave 5 beyond synthetic-only coverage by adding repo-curated real
    transcript fixtures for professional handoff and contradiction-preserving
    false-coherence review, keeping the same gate surface while giving the
    newer ITIR stories a stronger canonical fixture base.
  - Added a read-only Wikipedia random-page lexer coverage harness split into
    two tools:
    - `scripts/wiki_random_page_samples.py` for live revision-locked random-page
      acquisition into replayable manifests
    - `scripts/report_wiki_random_lexer_coverage.py` for offline scoring over
      stored manifests using both raw tokenizer diagnostics and the supported
      shared-reducer surface
  - Added focused tests plus a short contract note for the new random-page
    harness, keeping live acquisition out of test/CI paths.
  - Split the random-page Wikipedia quality story into two explicit stages:
    reducer/tokenizer coverage remains the stage-1 structural diagnostic, while
    a new general-text timeline readiness harness scores the deterministic
    `wiki_timeline_extract -> wiki_timeline_aoo_extract` path as the Mary-like
    chronology/event surface for broad text.
  - Added a parent random-page article-ingest contract and a new offline
    `scripts/report_wiki_random_article_ingest_coverage.py` scorer so broad
    arbitrary Wikipedia pages are now assessed first as article-wide sentence
    ingestion plus actor/action/object extraction, with timeline readiness and
    reducer/tokenizer reporting kept as companion surfaces rather than the only
    quality signal.
  - Realigned the Wikipedia ingest architecture around one canonical
    wiki-state compiler (`src/wiki_timeline/article_state.py`) plus three
    projections: article-ingest coverage, timeline, and revision/state diff.
    The timeline surface now keeps ordered undated events with explicit anchor
    status instead of pretending only dated rows exist, and the revision
    harness now compares canonical wiki state before surfacing graph/timeline
    reviewer summaries.
  - Extended `scripts/wiki_random_page_samples.py` with bounded one-hop
    followed-page acquisition metadata and replayable child snapshot linkage,
    keeping discovery capped while making cross-page follow testing explicit.
  - Added focused tests for article-wide sentence surface building, article
    ingest report aggregation, and one-hop random-page manifest behavior.
  - Added generic fact-review run query/report helpers plus
    `scripts/query_fact_review.py`, so existing persisted runs can be listed
    and inspected via run summaries, review queues, contested-item summaries,
    chronology-focused reporting, or the full stored fact-intake report.
  - Tightened transcript/AU review bundles with richer review queues and
    explicit `contested_summary` / `chronology_summary` sections so operator
    triage is clearer without changing the canonical substrate.
  - Added persisted `fact_workflow_links` mapping so transcript/AU semantic
    runs can be reopened deterministically as fact-review runs without
    rerunning the source workflow, and extended `scripts/query_fact_review.py`
    with workflow-based resolution/reporting alongside direct fact-run lookup.
  - Tightened canonical review triage in `build_fact_review_run_summary(...)`
    with bounded reason codes/labels, chronology buckets, workflow-link
    visibility, contested chronology impact summaries, and additive workflow
    metadata on listed runs.
  - Expanded the observation-layer legal/procedural visibility contract to
    carry AU semantic predicates such as `appealed`, `challenged`,
    `heard_by`, `decided_by`, `applied`, `followed`, `distinguished`, and
    `held_that` directly into fact-review observations while keeping event
    assembly rules unchanged.
  - Added latest-workflow resolution and implicit latest-by-workflow reopen
    behavior to `scripts/query_fact_review.py`, plus clearer workflow/reopen
    metadata in the transcript/AU fact-review operator scripts so operators can
    reopen persisted runs without copying IDs manually.
  - Tightened review-queue usability with primary contested reason text,
    latest review note/status, chronology-impact flags, legal/procedural
    observation flags, stable actionable ordering, and additive summary counts
    for follow-up, chronology impact, and legal/procedural-heavy queue items.
  - Added grouped chronology triage output (`dated_events`,
    `undated_events`, `facts_with_no_event`, `contested_chronology_items`)
    to the canonical fact-review summary and the transcript/AU review-bundle
    payloads, keeping the underlying event/fact chronology intact while making
    barrister/judge/CLC-style review faster.
  - Added role-meaningful review-queue issue codes
    (`missing_date`, `missing_actor`, `contradictory_chronology`,
    `statement_only_fact`, `procedural_significance`, `source_conflict`),
    bounded operator views (`intake_triage`, `chronology_prep`,
    `procedural_posture`, `contested_items`), and a read-only
    `fact.review.workbench.v1` payload over persisted runs.
  - Added story-driven acceptance reporting
    (`fact.review.acceptance.v1`) over persisted fact-review runs plus
    source-label-centric run listing in `scripts/query_fact_review.py`.
  - Added the first thin `itir-svelte` fact-review workbench at
    `/graphs/fact-review`, consuming the same persisted workbench/acceptance
    contract rather than introducing a second backend.
  - Added a canonical Wave 1 legal acceptance fixture manifest
    (`data/fact_review/wave1_legal_fixture_manifest_v1.json`) plus
    `scripts/run_fact_review_acceptance_wave.py`, so transcript/AU-backed and
    synthetic Mary-parity fixtures can be rebuilt and checked as one batch
    acceptance gate instead of one run at a time.
  - Tightened acceptance reports with failed-check IDs, blocking explanations,
    and bounded gap tags, and added a batch acceptance rollup contract so
    legal-story pass/partial/fail results can drive the next backlog slice.
  - Tightened legal-operator review summaries and workbench payloads with
    grouped intake issue filters, source-type/signal classification,
    approximate chronology grouping, and clearer distinction between party
    assertion, procedural outcome, and later annotation.
  - Tightened the persisted Mary-parity workbench contract further with
    explicit `reopen_navigation`, canonical `issue_filters`, and
    per-fact/workbench `inspector_classification` fields so downstream
    consumers no longer need to infer those operator surfaces from incidental
    payload shape.
  - Widened the AU fact-review adapter with additive legal/procedural surface
    cues for `claimed`, `denied`, `ordered`, and `ruled`, keeping them as
    observation/report signals rather than new event triggers.
- Branch-set ontology population hardening:
  - Kept the canonical deterministic lexer pre-semantic and moved AU/NSW
    branch-set identity resolution into a downstream reviewed bridge alias-scan
    path keyed by explicit anchor maps, preserving the documented extraction /
    enrichment boundary.
  - Added bridge fallback from `act_ref` occurrences to reviewed
    `legislation_ref` bridge rows so richer prepopulation slices remain
    authoritative without breaking deterministic batch emission.
  - Added evidence-carrying `match_receipts[]` metadata for text-driven bridge
    batches, optional receipt persistence from the batch emitter, and a
    read-only `ontology bridge-receipts-report` CLI for branch-set debugging.
  - Added end-to-end AU native-title, NSW liability/statute, and GWB
    institutions/courts branch tests covering bridge import, reviewed alias
    matching, explicit anchoring, and dry-run external-ref upsert coverage.
  - Extended the reviewed prepopulation slice with the AU judicial-review /
    NSW native-title branch (`Plaintiff S157/2002 v Commonwealth of Australia`,
    `Migration Act 1958`, `Native Title (New South Wales) Act 1994`) and
    aligned the reviewed court aliases so `High Court` resolves through the
    bridge rather than through canonical token identity.
  - Extended the same reviewed slice into the AU liability lane with
    `Commonwealth v Introvigne` and `Nationwide News Pty Ltd v Naidu`, plus
    receipt-backed batch tests for vicarious-liability / non-delegable-duty
    branch text.
  - Normalized legacy AU seed-time government `institution_ref` values into
    bridge-compatible downstream `jurisdiction_ref` / `organization_ref`
    rows during AU linkage import, so Commonwealth/NSW branches align with the
    reviewed bridge slice without reintroducing semantic identity into the
    canonical tokenizer.
  - Re-proved the AU state/statute lanes under that normalized importer
    (`Native Title (New South Wales) Act 1994`, `Civil Liability Act 2002
    (NSW)`) and added a mixed AU+GWB shared-DB regression so AU linkage
    normalization does not perturb the existing GWB semantic pipeline.
  - Extended the AU linkage report to expose normalized stored `seed_refs`
    directly, and added a seeded-slice isolation regression proving GWB
    bridge receipts stay bound to `seeded_body_refs_v1` even when the AU
    prepopulation slice is also present in the same database.
  - Added report-level visibility for AU normalized downstream refs and
    strengthened mixed-slice isolation checks so seeded GWB bridge/export
    runs remain explicitly pinned even in multi-slice databases.
  - Extended the reviewed prepopulation slice with the NSW branch set
    (`New South Wales`, `Civil Liability Act 2002 (NSW)`, `House v The King`,
    `New South Wales v Lepore`) using mixed reviewed providers where Wikidata
    was not the best available authority surface.
  - Added downstream relation/export checks for AU and NSW branch refs and
    restored graph-model compatibility aliases used by the external-ref triple
    tests.
- Environment/test entrypoint hardening:
  - Standardized `SensibLaw` operator and test docs on the superproject venv
    at `../.venv`.
  - Added `scripts/run_tests.sh` as the canonical pytest entrypoint.
  - Made the test harness fail fast with a targeted interpreter error when
    `pdfminer.six` is unavailable under the active Python.
- Wikidata / ontology bridge hardening:
  - Expanded deterministic bridge/report support to handle multi-provider
    reviewed slices cleanly across Wikidata and DBpedia, including richer
    `bridge-report` stats by provider/kind plus duplicate alias / duplicate
    external-id reuse diagnostics.
  - Updated bridge batch emission so a single canonical ref can emit both
    actor- and concept-anchored external refs and preserve provider-specific
    URLs for both Wikidata and DBpedia.
  - Added a bounded `prepopulation_core` Wikidata diagnostics profile over
    `P31`, `P279`, `P361`, and `P527` for CLI/data-contract-only review packs.
  - Flagged the existing Wikidata ontology test-suite interface in the working
    group/report docs as a first-line debug/function surface for the sprint.
- Assumption-stress controls hardening:
  - Added fail-closed control registry and waiver receipt scaffolding for
    `A1..A10` (`docs/planning/assumption_controls_registry.json`,
    `docs/planning/waivers/assumption_controls_waiver_20260311.md`) with CI
    guard tests in `tests/test_assumption_controls_fail_closed.py`.
  - Added initial `A1/Q1` executable axis-policy fixtures via
    `src/sensiblaw/ribbon/axis_policy.py` and
    `tests/test_ribbon_axis_policy.py` (collision detection + deterministic
    2D fallback semantics).
  - Added `A3` claim-link provenance quality gates in
    `src/reporting/narrative_compare.py`: public causal links
    (`supports`/`undermines`) now require `link_type`, `confidence`, and
    `counter_hypothesis_ref`; comparison/validation payload builds now fail
    closed when those fields or matching receipts are missing.
- Engine/profile followthrough (v1): added a concrete profile admissibility and
  lint baseline in `src/text/profile_admissibility.py` plus cross-profile
  safety tests in `tests/test_profile_admissibility.py`. The new slice enforces
  profile-local allowlists (`sl_profile`, `sb_profile`, `infra_profile`),
  preserves canonical `tokens[]`, rejects unanchored/out-of-bounds spans, and
  filters forbidden groups/axes/overlays without mutating tokenization.
- Tokenizer migration verification refresh: reran the deterministic migration
  regression lane in the project venv (`.venv`) over
  `tests/test_deterministic_legal_tokenizer.py`,
  `tests/test_lexeme_layer.py`, and
  `tests/test_tokenizer_migration_sl_regression.py` with all tests passing
  in one bounded run. This is a verification/synchronization update; canonical
  tokenizer behavior remains `deterministic_legal`.
- OpenRecall integration: add the first bounded observer import lane. New
  `scripts/import_openrecall.py` imports vendored OpenRecall `entries` rows
  into normalized `itir.sqlite` capture tables/read models, preserves capture
  provenance, exposes `load_openrecall_units(...)` for source-local semantic
  reuse, and feeds mission-lens actual-side reports as `openrecall_capture`
  activity rows without promoting raw OCR into canonical mission/semantic
  truth.
- OpenRecall integration: add the first neutral query/read-model interface
  over imported captures. `src/reporting/openrecall_import.py` now exposes
  latest-run, summary, and recent-capture query helpers, and
  `scripts/query_openrecall_import.py` provides a bounded JSON CLI for
  `runs`, `summary`, and `captures` without introducing GUI-first coupling or
  bypassing the observer-first ingest boundary.
- OpenRecall integration: add a bounded raw-row staging scaffold. New
  `src/reporting/openrecall_raw_import.py`,
  `scripts/import_openrecall_raw_rows.py`, and
  `scripts/query_openrecall_raw_import.py` can copy source `entries` rows into
  additive staging tables for inspection and migration work while keeping the
  normalized observer import as the canonical OpenRecall-to-ITIR path.
- NotebookLM metadata/review parity: added the first neutral NotebookLM
  observer read-model in `src/reporting/notebooklm_observer.py` plus bounded
  JSON CLI `scripts/query_notebooklm_observer.py`. The new slice summarizes
  NotebookLM date/notebook/source/artifact coverage from
  `runs/<date>/logs/notes/*.jsonl`, exposes recent-event queries, and projects
  source summaries/snippets into `TextUnit`s for downstream structure/semantic
  reuse without pretending `notes_meta` is a true activity ledger.
- NotebookLM interaction capture: added the first separate interaction lane
  over NotebookLM conversation history and notes. New
  `StatiBaker/scripts/capture_notebooklm_activity.py` and
  `StatiBaker/adapters/notebooklm_activity.py` emit additive
  `conversation_observed` / `note_observed` rows under
  `signal: notebooklm_activity`, while
  `src/reporting/notebooklm_activity.py` and
  `scripts/query_notebooklm_activity.py` provide query/read-model helpers and
  preview `TextUnit` projection from normalized outputs in
  `runs/<date>/outputs/notebooklm/`. The lane remains explicitly outside
  dashboard/session accounting.
- Wikipedia revision monitor: extend the lane into a bounded contested-region
  graph workflow. The runner now persists contested graph artifacts plus
  SQLite read-model tables for graphs/regions/cycles/edges, run summaries now
  emit pack-level contested graph triage, and article rows now expose
  contested graph refs/summaries directly. A new curated
  `data/source_packs/wiki_revision_contested_v2.json` pack enables deeper
  history windows and graph generation for contested pages, and
  `itir-svelte` now has a dedicated read-only page at
  `/graphs/wiki-revision-contested` backed by
  `SensibLaw/scripts/query_wiki_revision_monitor.py`.
- Tooling: add `SensibLaw/scripts/wiki_revision_runset.py` as a tiny wrapper
  for the common Wikipedia revision-monitor command sets (`tests`, one-article
  `smoke`, ontology-stress `monitor`, contested `contested`, and `all`).
- Docs/TODO alignment: add the first concrete OpenRecall integration posture.
  The suite now treats vendored `openrecall/` as an upstream local-first
  observer/capture source that should enter ITIR through normalized
  append-only import/read-model surfaces, feed mission-lens actual rows and
  source-local text reuse, and remain non-authoritative on ingest.
- Wikipedia revision monitor: upgrade the runner to a bounded history-aware
  lane. `scripts/wiki_pull_api.py` now supports bounded revision-history
  manifests plus exact revision fetches, and
  `src/wiki_timeline/revision_pack_runner.py` now polls recent revision
  windows, scores candidate deltas (`last_seen_current`, `previous_current`,
  `largest_delta_in_window`, `most_reverted_like_in_window`), computes
  section-delta summaries, selects only the top bounded pairs, persists
  history/candidate rows in the dedicated SQLite state DB, and emits
  pair-aware wrapper reports around the existing v0.1 revision harness output.
  Cross-project interface docs now explicitly define this lane as
  observer-only for `StatiBaker`, read-only hypothesis input for
  `SL-reasoner`, and reference-only for `fuzzymodo` and
  `casey-git-clone`.
- Docs/TODO alignment: clarify the current wiki revision monitor doctrine.
  The priority is not immediate `itir-svelte` integration; it is bringing the
  revision lane up to the same functional standard as the stronger suite
  pipelines via deterministic producer-owned outputs, queryable run/result
  state, additive read models, and shared provenance/review posture so other
  pipelines can reuse the lane cleanly.
- Narrative validation/comparison: the thread-derived FriendlyJordies fixture
  now normalizes two more comparison seams from the live discussion instead of
  leaving them as unrelated source-only text. `friendlyjordies_thread_extract`
  now aligns `contribute_to` vs `delay` as a shared CPRS consequence family,
  treats the Woolworths `direct grocery impacts` vs `direct cost pass-through`
  lines as a shared statement family, and emits explicit cross-source
  `undermines` links for both disputes.
- Narrative validation/comparison: the FriendlyJordies comparison lane now
  also normalizes the government-formation argument seam. Claims like
  `majority government supports long-term climate policy` and
  `minority government passed carbon pricing legislation` now compare as a
  shared `government_climate_policy_capacity` family and emit a structured
  `undermines` link instead of surviving as source-only leftovers.
- Narrative validation/comparison: widen the proposition layer to preserve
  nested authority wrappers in public-media fixtures. The comparison extractor
  now recursively emits chains like `assert/report -> hold -> fact`, adds a
  public `friendlyjordies_authority_wrappers.json` proving fixture, preserves
  full attribution stacks in comparison output, and derives bounded cross-
  source `undermines` links for conflicting same-outcome causal claims.
- Wikipedia revision pack runner: add the first bounded rolling-runner contract
  and article pack for current-vs-last-seen monitoring. The design uses a
  dedicated SQLite state store, selected article manifests under
  `data/source_packs/`, store-first revision comparisons, and hybrid review
  context (curated pack context first, bounded bridge/alias auto-join second).
- Wikipedia revision monitoring: add a second curated article pack,
  `data/source_packs/wiki_revision_contested_v1.json`, for high-contestation
  live pages across politics, ongoing conflict, religion, and politicized
  science/medicine. The new planning note
  `docs/planning/wiki_revision_contested_pack_20260309.md` records the source
  thread (`Highly Contested Wiki Pages`,
  `69ada623-351c-839a-97c4-7669a12b8e04`, source `web`) and keeps this pack
  explicitly complementary to the ontology-stress monitor pack instead of
  replacing it.
- Narrative validation/comparison: add a second public FriendlyJordies-derived
  argument fixture (`friendlyjordies_chat_arguments.json`) based on the archive
  discussion itself. The bounded comparison extractor now also recognizes
  argument predicates such as `block`, `contribute_to`, `use`, `support`,
  `pass`, and `govern_in`, and comparison treats same-outcome / different-cause
  claims as disputes instead of unrelated source-only rows.
- Wikipedia revision harness: add a bounded read-only comparison/report lane
  for previous-vs-current Wikipedia revisions. New contract/docs define the
  v0.1 report shape (similarity metrics, extraction delta summary, local
  graph-impact summary, epistemic delta summary, issue packets, triage
  dashboard), and `scripts/wiki_revision_harness.py` now compares revision
  snapshots plus optional AAO payloads without mutating ontology rows or
  generating edit-bot actions.
- Narrative validation/comparison: add a bounded public-media fixture and
  producer-owned comparison lane for FriendlyJordies-style media validation.
  `SensibLaw/scripts/narrative_compare.py` now emits source-local validation
  reports plus a `narrative_comparison_report` over two sources with shared
  propositions, disputed propositions, source-only claims, attribution-link
  differences, corroboration refs, and abstentions. The first slice is
  fixture-first and read-only, using the checked-in
  `SensibLaw/demo/narrative/friendlyjordies_demo.json` corpus.
- Docs/TODO alignment: add
  `docs/planning/friendlyjordies_narrative_validation_and_competing_narratives_20260309.md`
  as the public-media narrative-validation and competing-narratives planning
  note. The docs now name FriendlyJordies as the first public transcript/media
  proving case, record the privacy boundary for private archive-derived
  examples, and queue proposition-layer widening toward cited holdings,
  attribution wrappers, and proposition comparison support.
- Archive tooling: extend `scripts/chat_context_resolver.py` beyond pure
  thread resolution. The resolver now also supports stitched transcript
  analysis for term frequency, mention locations with thread-line and
  per-message line numbers, line/message range excerpts, simple top-term
  extraction, and archive-wide cross-thread ranking by mention counts/density.
- Semantic review feedback: move the semantic workbench correction seam out of
  local JSONL and into append-only `itir.sqlite` tables
  (`semantic_review_submissions` + `semantic_review_evidence_refs`), with a
  small admin/query CLI so `itir-svelte` can submit/load recent corrections
  without becoming a storage authority.
- Transcript/freeform semantics: reports now emit a bounded
  `mission_observer` artifact plus SB-safe observer overlays for explicit
  mission/follow-up cues. Current v1 resolves local follow-up references
  conservatively, carries forward grounded deadlines, and abstains on
  unresolved referents.
- Transcript/freeform semantics: persist the `mission_observer` artifact
  canonically into normalized `itir.sqlite` mission tables
  (`mission_runs`, `mission_nodes`, `mission_edges`,
  `mission_evidence_refs`, `mission_observer_overlays`,
  `mission_overlay_refs`) and reload reports from that DB-backed read model.
- Mission lens: add the first ITIR-owned planning substrate on top of the
  persisted mission observer lane with `mission_plan_nodes`,
  `mission_plan_edges`, `mission_plan_deadlines`, and
  `mission_plan_receipts`. The new `SensibLaw/scripts/mission_lens.py` builds a
  fused actual-vs-should artifact against SB dashboard data and exposes bounded
  plan-node authoring for the new mission workbench.
- Mission lens: add DB-backed reviewed actual-to-mission linking in
  `itir.sqlite` via `mission_actual_mappings` and
  `mission_actual_mapping_receipts`. The mission-lens report now prefers
  reviewed activity links over lexical fallback and emits concrete activity-row
  mapping state for UI review.
- Semantic reporting: transcript and GWB/AU report builders now emit a shared
  producer-owned `text_debug` artifact with tokenization, anchor provenance,
  relation-family metadata, and confidence-derived display opacity so the
  `itir-svelte` workbench no longer needs to re-derive semantic anchors in TS.
- Semantic reporting: GWB/AU/transcript reports now also emit a shared
  `review_summary` artifact with compact predicate counts, cue-surface counts,
  and `text_debug` coverage/exclusion totals so review surfaces can compare
  corpora without relying on raw relation tables.
- Semantic reporting: `text_debug` anchors now carry producer-owned char spans
  and `sourceArtifactId` values alongside token ranges, giving the workbench a
  real shared span contract for future graph/document linking without treating
  spans as canonical semantic provenance.
- Semantic reporting: transcript/freeform reports now also emit grouped source
  document payloads plus source-level event spans, allowing the semantic
  workbench to cross-highlight into real source text without deriving document
  offsets in TS.
- Semantic reporting: GWB/AU reports now also emit grouped timeline-source
  payloads plus source-level event spans from the normalized wiki timeline
  store, so the semantic workbench source viewer can render real legal-lane
  source text without TS-side reconstruction.
- Semantic rule substrate: add shared DB-backed metadata for
  `semantic_rule_types`, `semantic_slot_definitions`, `semantic_rule_slots`,
  and `semantic_promotion_policies` around the frozen event-scoped semantic
  spine. GWB/AU/transcript predicate vocab now seeds bounded rule-family and
  promotion-gate policy rows. Candidate insertion now reads predicate-level
  policy metadata to decide `promoted` vs `candidate` status, and emitted
  candidate/promoted receipts now carry explicit rule-family and promotion
  policy traces. Confidence derivation now also consults shared policy
  evidence requirements as a conservative downgrade layer while remaining
  profile-local for now, and the shared selector-interpreter question is
  explicitly deferred.
- Docs/TODO alignment: add
  `docs/planning/semantic_rule_slots_and_promotion_gates_20260308.md`, record
  the decision in `COMPACTIFIED_CONTEXT.md`, and add the follow-up TODO to move
  current predicate heuristics toward the shared slot/rule/promotion substrate
  incrementally rather than via another schema rewrite.
- Shared actor identity governance: add a shared actor layer around the frozen
  semantic spine with `actors`, `actor_aliases`, `actor_merges`, and
  `event_role_vocab`. Actor-like semantic entities now attach via
  `semantic_entities.shared_actor_id`, reviewed actor aliases persist
  canonically across GWB/AU/transcript lanes, and `semantic_event_roles`
  consume governed role keys instead of remaining entirely untracked free text.
- Transcript/freeform semantics: tighten the generalized freeform entity
  heuristics so obvious titlecase noise no longer becomes a source-local actor.
  The bounded single-token gates now keep contextual person/place surfaces such
  as `Picasso` and `Brisbane`, while dropping non-entity openings like
  `Thanks`, `Today`, and role/system labels from the general entity lane.
- Transcript/freeform semantics: generalize the bounded transcript semantic
  lane into the first profile-neutral SL human-text baseline. Freeform/journal
  text now gets broad source-local actor/entity extraction, explicit object
  themes can persist as source-local concepts, and explicit affect cues can
  emit candidate-only `felt_state` relations without promoting non-legal mood
  semantics or loading legal predicates by default.
- Transcript semantic lane: add a bounded transcript/freeform semantic v1
  adapter over existing `TextUnit` + speaker-inference inputs. The first pass
  persists source-local speaker mention resolution and `speaker` event roles in
  the shared semantic tables, abstains on timing-only and role-only non-person
  cases, and emits candidate-only `replied_to` conversational relations rather
  than forcing promotion.
- Transcript/freeform tooling: add `SensibLaw/scripts/transcript_semantic.py`
  as a deterministic run/report entrypoint over the existing transcript
  semantic lane, including a bounded built-in demo corpus for downstream
  workbench/debug consumers such as `itir-svelte`.
- Transcript/freeform semantics: add a first bounded explicit social-relation
  slice for named kinship/friendship statements (`sibling_of`, `parent_of`,
  `child_of`, `spouse_of`, `friend_of`) plus explicit guardian/care surfaces
  (`guardian_of`, `caregiver_of`). These relations remain candidate-only by
  default, emit `social_relation` rule receipts, and may attach
  `related_person` event-role context when both actors are explicit in the
  same text span.
- Transcript/freeform semantics: normalize care relation naming so the
  canonical predicate is tense-neutral (`caregiver_of`) while observed
  wordings such as `cared for`, `cares for`, and `looks after` stay in
  receipts only. The transcript report entrypoint now also exposes a compact
  `summary` mode for predicate/cue review.
- GWB U.S.-law linkage: tighten broad cue handling for `Congress`, `Iraq`,
  `veto`, and `Supreme Court` so weak broad-surface evidence can remain visible
  as low-confidence matched/candidate output when unambiguous, but no longer
  inflates medium/high confidence without stronger non-broad receipts.
- AU semantic extraction: move legal-representation cue surfaces into a
  versioned lexical resource, expand them from parameterized party-role
  templates, and require a clause-local named representative signal before
  `appeared for ...` / `counsel for ...` cues resolve. Cue matches now attach
  to real document-local representative actors instead of creating synthetic
  role-label actors.
- Wikidata bridge seeding: make seeded-slice initialization payload-aware so
  alias updates refresh deterministically (`source_sha256` mismatch triggers
  in-place seeded slice replacement), preventing stale local DB slices from
  hiding newly reviewed aliases.
- Wikidata bridge/GWB/AU semantic follow-through: add reviewed district-court
  alias variants to the pinned bridge slice, extend GWB deterministic promoted
  relation coverage into review/litigation predicates
  (`ruled_by`, `challenged_in`, `subject_of_review_by`), and tighten AU
  legal-representative extraction with expanded role surfaces plus dotted
  suffix handling for `S.C./K.C./Q.C.` style mentions.
- Wikidata review workflow: record a pinned-slice baseline policy for bounded
  ontology diagnostics (latest pinned snapshot as default, historical rewind
  review as an explicit follow-up when ambiguity/reversion risk is flagged).
- Wikidata review workflow: complete follow-on qualifier-review actions by
  validating `medium` signature-only severity on the two pinned confirmed cases
  (`Q100104196|P166`, `Q100152461|P54`), and classifying `Q100243106|P54` as
  a historical watch candidate instead of a pinned case until revalidated.
- Wikidata docs/status sync: separate the repo-pinned qualifier review pack
  from fresh live rerun output, keeping `Q1000498|P166` as a newly confirmed
  live candidate while the pinned review pack remains on
  `Q100104196|P166` and `Q100152461|P54`.
- Docs/TODO/status alignment: add bounded extraction-vs-enrichment, mereology,
  and property/constraint pressure-test notes; link them from the working-group
  status and core boundary docs; and update TODO checkpoints to reflect the
  completed bridge/semantic/doc milestones.
- StatiBaker boundary tests: add the three small deterministic SL -> SB
  invariant checks at the actual overlay-ingest boundary: segmentation
  preservation, canonical ID preservation, and no summary injection. Summary/
  synthetic segment fields are now explicitly forbidden by the current ingest
  contract.
- Clarify the SB boundary explicitly: SB only consumes or extends SL-owned
  lexer/compression outputs for shell/message/transcript-style workflows. The
  current legal-labelled SB fixtures are opaque SL-origin canonical payloads
  used for preservation tests only, not evidence of legal semantics moving
  into SB.
- Docs/boundaries: align the main SB and SL docs on the same statement that SB
  is a personal state compiler feeding TiRC/ITIR, and that shared
  lexer/compression reuse from SL does not transfer semantic or legal
  authority into SB/TiRC.
- Semantic cross-testing: add an Australian legal cross-test proving the
  frozen v1.1 `entity -> mention_resolution -> event_role -> relation_candidate
  -> semantic_relation` shape can express court/forum/authority/review
  patterns without schema changes.
- Australian semantic lane: extend the first proving pass with deterministic
  legal-representative surfaces, explicit office surfaces
  (`Attorney-General`, `Registrar`), broader doctrinal/review candidate
  coverage, and `scripts/au_semantic.py import-seed` so the lane can be run
  against live `itir.sqlite` data without ad hoc imports.
- Docs/planning: make the Australian corpora the explicit cross-test source for
  the frozen semantic v1.1 phase and keep the bounded Wikidata
  mereology/property-pressure lane supportive of that pressure-testing rather
  than a reason to widen canonical schema early.
- Docs/planning: sync two freshly archived design threads into the current
  semantic and reducer-boundary plans. The GWB semantic note now freezes the
  v1.1 invariants more explicitly (unified entity spine, first-class mention
  resolution, three-step relation promotion, courts as classified
  institutions, discourse labels like `Bush administration` non-canonical by
  default), and the SL -> SB reducer contract now names the three small
  fixture-driven integration tests that should close most remaining boundary
  risk: segmentation preservation, canonical ID preservation, and no summary
  injection.
- GWB semantic layer v1.1: tighten the proving lane around the frozen unified
  entity spine. `the President` and `the court` now abstain by default instead
  of resolving too early, low-support edges remain visible as
  `relation_candidate` rows with `promotion_status='candidate'`, and the
  report now splits promoted, candidate-only, and abstained relation outputs
  explicitly.
- GWB semantic layer: add a first DB-backed semantic spine on top of the
  reviewed Bush U.S.-law linkage lane. New storage now includes a unified
  entity spine, office-holding rows, mention-resolution artifacts, event-role
  rows, predicate vocabulary, relation candidates, and promoted semantic
  relations. Current v1 promotes conservative `nominated`, `confirmed_by`,
  `signed`, and `vetoed` edges while keeping broader political/discourse labels
  like `Bush administration` non-canonical by default.
- Wikidata docs/planning: sync the archived "Wikidata Ontology Issues" thread
  into the current working-group plan by adding a bounded next-step direction
  for mereology/parthood typing and explicit TODOs around a DASHI-compatible
  formalism for typed/disambiguated parthood diagnostics. No code changes in
  this pass.
- Wikidata docs/planning: fold additional Telegram/working-group points into
  the bounded ontology lane: property definitions/constraints are in scope when
  they interact with classes, financial-flow/timeseries modeling is a valid
  pressure-test surface, label harmonization is a diagnostic clue rather than
  ontology truth, and the mereology lane should anchor on the actual parthood
  property family (`P527`, `P361`, etc.).
- GWB U.S.-law linkage: expand the reviewed Bush U.S.-law seed from the
  original starter pack into an 11-lane checked-in corpus sweep, add shared-DB
  seed/import/match/receipt tables plus `scripts/gwb_us_law_linkage.py`, and
  run the deterministic matcher/reporter against the live GWB timeline in
  `itir.sqlite`. Current live result: `142` events, `15` promoted matches, `8`
  ambiguous events, and all `11` reviewed seeds surfaced in the report. Broad
  cue-only lanes (`Congress`, `Iraq`, `veto`, `Supreme Court`) remain the next
  tightening target.
- Docs/privacy: make the local-only policy explicit for personal
  archive-derived test DBs. Isolated chat/Messenger experiment stores under
  `.cache_local/` are not canonical/shared artifacts and must never be
  promoted into checked-in repo storage.
- Message archives: tighten the bounded Messenger/Facebook importer with
  deterministic keep/drop reason categories, persist per-run filter counts, and
  add `scripts/report_messenger_test_tokenizer_stats.py` so Messenger test DB
  runs can be reported without ad hoc Python snippets.
- Reporting/ops lane: reduce slash-heavy prose false positives in
  `path_ref` detection and add a compact side-by-side comparison summary for
  `report_structure_corpora.py --by-source`.
- Reporting/ops lane: add Messenger test DB support to the shared
  `report_structure_corpora.py` input surface, tighten Messenger URL/rate
  shorthand false positives further, and start the deterministic
  speaker-inference implementation with explicit receipts plus abstention on
  timing-only subtitle ranges.
- Reporting/ops lane: strip URL schemes before `path_ref` slugging so
  canonical path atoms stay in host/path form (`path:chatgpt_com_share_...`)
  and add `scripts/report_speaker_inference_corpora.py` for deterministic
  speaker-inference reporting across Messenger/chat/context/transcript corpora.
- Speaker inference: implement the first conservative carry-over rule
  (`neighbor_consensus`) for single-gap `insufficient_evidence` units bracketed
  by the same explicit speaker, while leaving broader multi-turn coalescence
  and disagreement/entropy heuristics as follow-up work.
- Reporting/relations: add `scripts/report_relation_neighborhoods.py` plus
  `src/reporting/relation_neighborhood_report.py` so corpus reports can rank
  top recurring terms and surface parser-local dependency/co-occurrence
  neighborhoods alongside reviewed bridge/Wikidata matches, without changing
  canonical lexeme identity.
- Docs: clarify that speaker inference is staged: current receipts-first v1 is
  implemented, conservative multi-turn coalescence is next, and
  disagreement/entropy heuristics remain a later reviewed layer.
- Docs: add `docs/planning/speaker_inference_v1_20260307.md` to define the
  deterministic speaker-inference boundary. Sentiment may act only as a weak
  secondary tie-breaker, never as a primary speaker assignment signal.
- Docs: clarify the extraction/enrichment boundary so `spaCy` dependency
  parsing is explicitly documented as deterministic local structural backup for
  relation/role harvesting, while Wikidata remains downstream
  identity/enrichment/diagnostic support and never canonical token identity.
- Lexeme/Wikidata bridge: expand the deterministic legal lexer to cover structural
  legal atoms (`act_ref`, `section_ref`, `subsection_ref`, `paragraph_ref`,
  `part_ref`, `division_ref`, `rule_ref`, `schedule_ref`, `clause_ref`,
  `article_ref`, `instrument_ref`) plus seeded institution/court references,
  while tightening ambiguity guards for prose false positives (`act`, `art`,
  `court`, `agreement`, `framework`, `part`, `division`, `rule`, `s/sec`,
  `r/rule` in non-legal contexts).
- Lexeme/Wikidata bridge: add a deterministic bridge layer
  (`src/ontology/entity_bridge.py`) so canonical lexer refs remain internal
  (`institution:united_nations`, `court:international_criminal_court`) while
  seeded external identity is attached downstream as Wikidata links
  (`wikidata:Q1065`, `wikidata:Q47488`, etc.).
- Lexeme/Wikidata bridge follow-through: normalize leading determiners in
  canonical act/instrument refs (e.g. collapse `the ... Agreement` to the same
  atom as the bare title), add a `structural_atoms` / `structural_atom_occurrences`
  dictionary in `VersionedStore` for high-yield legal kinds, and add
  `scripts/emit_bridge_external_refs_batch.py` so bridge hits can be emitted as
  curated `ontology external-refs-upsert` payloads for the existing
  `actor_external_refs` / `concept_external_refs` substrate.
- Benchmarks/reports: extend `scripts/benchmark_tokenizer_corpora.py` to
  report both structural legal-atom capture and linked-entity capture across
  GWB, legal fixtures, mixed legal-reference text, and GWB-derived reference
  snippets; add `scripts/report_canonical_atom_frequency.py` to quantify
  repeated structural atoms separately from linked entities for DB-dedupe
  planning.
- Reporting/structure lane: tighten operational false positives, generalize the
  transcript parser from app-specific WhatsApp-style lines to generic
  bracketed/unbracketed timestamped message transcripts, collapse duplicate
  time-only transcript atoms when a full date-time atom is present, add
  canonical transcript timestamp normalization (`ts:YYYY_MM_DD_HH_MM`), add
  transcript range normalization (`timestamp_range_ref` /
  `tsrange:START__END`) for subtitle-style timing lines, split transcript files
  into message/range units instead of coarse paragraph blocks, add a checked-in
  Telegram-style transcript fixture, add
  `--by-source` side-by-side corpus comparison support to
  `scripts/report_structure_corpora.py`, and validate the transcript lane
  against both the in-repo bracketed-message fixture and a real sample under
  `/home/c/Documents/code/__OTHER/tirc_test_audio`.
- Message archives: add `scripts/ingest_messenger_sample_to_itir_test_db.py`
  for bounded Messenger/Facebook archive ingestion into an isolated test DB,
  filtering obvious archive/system rows and emitting message-shaped units from
  `sender`, `message`, and `time_sent` instead of treating the export as a raw
  blob.
- Transcript/chat parser cleanup: remove transcript unit/header regex logic
  from `src/reporting/structure_report.py` and move deterministic message/range
  parsing into `src/text/message_transcript.py`, keeping regex out of the
  transcript/chat path as far as practical.
- Tests: expand deterministic tokenizer/lexeme coverage for legal structural
  atomization, seeded institution/court linking, negative ambiguity suites, and
  benchmark semantics (`tests/test_deterministic_legal_tokenizer.py`,
  `tests/test_lexeme_layer.py`, `tests/test_tokenizer_benchmark_semantics.py`,
  plus the existing swallow/compression guards).
- Wiki timeline DB: canonical runtime path now targets the shared ITIR root DB
  (`ITIR_DB_PATH`, default `./.cache_local/itir.sqlite`) instead of the
  wiki-specific sidecar SQLite file; old `SL_WIKI_TIMELINE_*` env vars are
  deprecated compatibility aliases.
- Wiki timeline DB: added `scripts/migrate_wiki_timeline_to_itir_db.py` for
  eager rewrite/import into the ITIR root DB, plus `tests/test_migrate_wiki_timeline_to_itir_db.py`.
- Wiki timeline DB: normalize canonical event storage around typed tables for sections,
  actions, actors, links, objects, steps, and list payloads; query paths now rebuild
  route payloads from normalized rows instead of monolithic `event_json` blobs.
- Wiki timeline DB: add lazy schema/backfill-on-read support in
  `src/wiki_timeline/sqlite_store.py` so existing DB files are upgraded when queried.
- Wiki timeline DB: add `scripts/wiki_timeline_storage_report.py` to measure legacy blob
  bytes versus normalized storage estimates per run.
- Lexeme: add a no-regex deterministic legal candidate tokenizer (`deterministic_legal_v1`)
  behind `ITIR_LEXEME_TOKENIZER_MODE=deterministic_legal`, including section/reference-aware
  spans and span-profile metadata in revision writes (`src/text/lexeme_index.py`,
  `src/text/deterministic_legal_tokenizer.py`).
- Tests: add `tests/test_deterministic_legal_tokenizer.py` covering deterministic behavior and
  legal reference atomization.
- Docs: add Wikidata statement-bundle epistemic projection operator spec with
  EII instability metric (`docs/wikidata_epistemic_projection_operator_spec_v0_1.md`).
- Docs: link the Wikidata projection operator spec from `README.md`.
- Docs: add Wikidata ontology issue review and diagnostics mapping
  (`docs/wikidata_ontology_issue_review_20260306.md`).
- Docs: link the ontology issue review from `README.md`.
- Docs: add `docs/ontology_diagnostic_taxonomy_wikidata_v0_1.md`, append the
  diagnostic-lens appendix to
  `docs/wikidata_epistemic_projection_operator_spec_v0_1.md`, and align
  `docs/external_ontologies.md` with the bounded `P31` / `P279` Wikidata
  control-plane posture and tokenizer/lexeme authority boundaries.
- Docs: add a reviewer handoff template for the Wikidata ontology working group
  (`docs/planning/wikidata_working_group_review_template_20260307.md`) and
  update the transition plan's next actions to reflect the completed phase-1
  doc work.
- Wikidata prototype: add a bounded `P31` / `P279` projection module
  (`src/ontology/wikidata.py`), deterministic SCC/mixed-order/metaclass
  diagnostics, and a `sensiblaw wikidata project` CLI path with JSON report
  output.
- Tests: add bounded Wikidata projection and CLI coverage
  (`tests/test_wikidata_projection.py`, `tests/test_wikidata_cli.py`).
- Wikidata docs/fixtures: add a small live-case fixture for the current
  `alphabet` / `writing system` example
  (`tests/fixtures/wikidata/live_p31_p279_slice_20260307.json`) and mark the
  `referendum` / `plebiscite` loop example as historical/thread-derived unless
  revalidated from current live data.
- Wikidata fixtures/tests: upgrade the live-case fixture into a true two-window
  review slice with a non-zero `Q9779|P31` EII example and add fixture-backed
  coverage in `tests/test_wikidata_projection.py`.
- Wikidata review/reporting: add a filled first review-pass note
  (`docs/planning/wikidata_working_group_review_pass_20260307.md`), define the
  v0.1 reviewer-facing report contract (`docs/wikidata_report_contract_v0_1.md`),
  and add severity buckets plus `review_summary` to the JSON report.
- Wikidata importer: add `sensiblaw wikidata build-slice` for building bounded
  `P31` / `P279` slices from local entity-export JSON files, with CLI coverage
  and fixture entity exports.
- Wikidata working-group pack: add a single status doc
  (`docs/wikidata_working_group_status.md`) as the stable working-group link,
  and expand the live review fixture with a confirmed current SCC example
  (`Q22652` <-> `Q22698`).
- Wikidata review pack: broaden the seeded live slice with an additional current
  mixed-order example (`Q21169592` -> `Q7187`) and an additional current live
  SCC pair (`Q52040` <-> `Q188`), then refresh the seeded review-pass notes and
  status summary to match.
- Wikidata qualifier drift: extend `sensiblaw wikidata project` with
  `qualifier_drift[]` reporting, qualifier property-set/signature/entropy
  comparison across windows, and add bounded phase-2 fixture/tests for a
  qualifier-bearing slot.
- Wikidata qualifier fixtures: add importer-backed real qualifier-bearing
  entity-export fixtures and a generated two-window baseline slice
  (`tests/fixtures/wikidata/real_qualifier_imported_slice_20260307.json`) so
  phase-2 review now includes real current/previous revision pairs alongside
  the bounded synthetic drift demo.
- Wikidata qualifier discovery: add `sensiblaw wikidata find-qualifier-drift`
  to rank current qualifier-bearing candidates, scan recent revisions
  deterministically, and emit a machine-readable report of confirmed drift
  cases, stable baselines, and fetch failures.
- Wikidata qualifier discovery: cheapen live candidate collection by switching
  to per-property raw-row WDQS queries (no label service, no `GROUP_CONCAT`, no
  `GROUP BY`) and allow partial success when one property query fails.
- Wikidata qualifier discovery: first successful broad live scan now yields
  confirmed medium-severity revision-pair drift cases, with the primary
  materialized example currently `Q100104196|P166`
  (`2277985537 -> 2277985693`) under `/tmp/wikidata_qualifier_scan/`.
- Wikidata qualifier fixtures/tests: promote the primary live drift case
  `Q100104196|P166` (`2277985537 -> 2277985693`) into
  `tests/fixtures/wikidata/q100104196_p166_2277985537_2277985693/` and add
  projector/CLI regression coverage for the repo-pinned materialized slice.
- Wikidata qualifier fixtures/tests: add a second repo-pinned live drift case
  `Q100152461|P54` (`2456615151 -> 2456615274`) so the phase-2 review pack now
  covers both `P166` and `P54`.
- Wikidata operator helper: add
  `scripts/run_wikidata_qualifier_drift_scan.py` to run the live finder,
  persist a scan report, and automatically materialize the first confirmed case
  into local entity-export, slice, and projection JSON artifacts.
- Docs: add `SensibLaw/todo.md` to track the remaining bounded-slice Wikidata
  implementation work and link the new taxonomy doc from `README.md`.
- Tests: add regex transition coverage for wiki timeline extraction and AAO
  extraction (including explicit xfail cases for known regex limitations).
- Docs: align finance schema and numeric representation with time-series
  transformation model and Niklas-style series derivation examples.
- Docs: define tokenizer transition goal (regex → deterministic multilingual),
  with checkpoint-parity requirement for graph hydration payloads.
- Wikipedia/HCA AAO extraction profile: add deterministic semantic-backbone
  guard/normalizer (`semantic_backbone.resource/wsd_policy/llm_enabled`) so
  non-deterministic profile settings fail fast and extraction metadata records
  authoritative non-generative semantic-lane configuration.
- NLP/AAO semantic backbone: add deterministic, version-pinned synset action
  mapping behind `semantic_backbone` (WordNet via local corpus + version pin;
  BabelNet via profile-provided lemma->synset table), with explicit
  `synset_action_map` and deterministic tie-break ordering.
- NLP/AAO semantic backbone: canonical synset mapping now follows "single-action
  or abstain" semantics (no silent choice between competing mapped actions).
- Wikipedia/HCA AAO semantic backbone: add deterministic sha256 pins for mapping
  tables:
  - `semantic_version_pins.babelnet_table_sha256`
  - `semantic_version_pins.synset_action_map_sha256`
  extractor fails fast on mismatch and emits computed table hashes in
  `extraction_profile`.
- Ingest: `source_pack_manifest_pull.py` now indexes local `seed_paths` (file
  sha256 + size + type) alongside fetched `seed_urls`, without copying local
  binaries into the output directory.
- NLP/AAO action extraction: add `src/nlp/event_classifier.py` and switch
  primary action selection to spaCy token lemma+dependency classification
  (parser-first), with regex action patterns retained as explicit fallback.
- Wikipedia/HCA AAO script runtime: add deterministic `sys.path` bootstrap for
  `SensibLaw/scripts/*` execution so `src.nlp.*` classifiers/mappers load
  consistently when invoked from repo root.
- Tests: add event-classifier coverage in
  `tests/test_event_classifier.py` and update claim-attribution regression for
  regex fallback warning semantics.
- Wikipedia timeline extraction: skip infobox/template residue sentence fragments
  (`| key = value` payload lines) during sentence pass so lead timeline rows are
  sourced from narrative text, not template artifacts.
- Tokenizer migration: regression suite runs in the project venv
  (`tests/test_deterministic_legal_tokenizer.py`, `tests/test_lexeme_layer.py`,
  `tests/test_tokenizer_migration_sl_regression.py`) with deterministic mode as
  canonical; offline extraction refreshed `SensibLaw/.cache_local/wiki_timeline_gwb*.json`
  so `/graphs/wiki-timeline*` payloads hash-match the checkpoint HTML (142 events each).
- Tokenizer guardrails: add offline parity checker `SensibLaw/scripts/check_wiki_timeline_parity_offline.js`
  and default-mode tests (`tests/test_tokenizer_default_mode.py`) to ensure canonical
  mode stays deterministic and route payloads remain aligned with checkpoints.
- Tokenizer swallow guard: add `tests/test_tokenizer_no_swallowed_tokens.py` to fail if
  the deterministic lexer emits whitespace-bearing tokens outside legal structural types
  or if word tokens over-swallow text.
- CI parity lane: add `tests/test_wiki_timeline_parity_offline.py` to run the offline parity
  checker under deterministic mode; fails on drift. Warn when legacy tokenizer mode is used
  via env (`ITIR_LEXEME_TOKENIZER_MODE=legacy_regex`). Added opt-in env
  `ITIR_ALLOW_REQUEST_REGEX` to keep requester regex fallback disabled by default.
- Compression sanity: add `tests/test_tokenizer_compression_efficiency.py` to bound average
  token length and token counts on plain sentences and legal references.
- Wiki timeline DB: route loaders now use the SQLite store for all sources; added manual ingests
  for legal/legal_follow timelines and `tests/test_wiki_timeline_db_presence.py` to fail CI when any
  configured suffix is missing in the DB.
- Wikipedia/HCA AAO action extraction: require pattern-match span overlap with
  verb/AUX tokens (when parser tokens exist) before accepting regex action
  matches, preventing noun-only nominalization leaks (e.g., `death` selecting
  `die`) from entering action lanes.
- Tests: add regression coverage for noun-vs-verb action matching and template
  residue sentence guards in
  `tests/test_wiki_timeline_claim_attribution.py` and
  `tests/test_wiki_timeline_extract_section_anchor.py`.
- Wikipedia timeline extraction: add deterministic inline year-range anchors
  (`from YYYY to YYYY` -> year mention at range start) and apply lead-sentence
  anchor preference to avoid birth-date day mentions dominating service-range
  biography clauses.
- Wikipedia/HCA AAO subject normalization: canonicalize root-actor partial name
  surfaces (e.g., `Walker Bush`) back to the configured root actor when token
  overlap/initials match, and hard-pin root surname alias resolution to root
  actor to reduce alias drift.
- Docs/contracts: expand inter-fact linking + duplicate guards for wiki fact
  timeline rows in `docs/planning/wiki_timeline_coalescing_contract_20260212.md`
  and add explicit requirements coverage in
  `docs/wiki_timeline_requirements_v2_20260213.md` (`R25`: event-local,
  chain-typed, non-causal fact coalescing/linking constraints).
- Ontology/Layer-3: formalize `LegalSystem` as a normative authority boundary
  (not a country label) in docs (`docs/ontology.md`, `docs/ontology_er.md`),
  including sovereignty tier, parent hierarchy, constitutional linkage, and
  common-law/equity recognition fields.
- DB (SQLite): add `004_legal_system_authority_contract.sql` migration to extend
  `legal_systems` with authority-boundary fields
  (`sovereignty_type`, `parent_system_id`, `commencement_date`,
  `constitutional_source_id`, `recognises_common_law`,
  `recognises_equity`), seed `CONSTITUTION` source category, backfill AU
  sub-sovereign system rows (`AU.STATE.*`), parent them to `AU.COMMON`, and
  link constitutional `legal_sources`.
- DB (Postgres/schema refs): add matching authority-boundary migrations
  (`database/postgres_migrations/005_legal_system_authority_contract.sql`,
  `schemas/migrations/005_layer1_legal_system_authority_contract.sql`).
- Tests: extend migration coverage with authority-boundary assertions in
  `tests/test_db_migrations_and_daos.py` (sovereignty tier, parent linkage,
  commencement date, constitutional source linkage).
- Wikipedia/HCA AAO numeric claims: recover dependency-scoped count units and
  quantity targets (`nummod -> unit head`, e.g., `71 lines of stem cells` ->
  `71|line` with `applies_to=stem cells`) and emit nearest DATE entity text as
  `numeric_claims[].time_text` for explicit date attribution in claim lanes.
- Tests: extend numeric-lane coverage in
  `tests/test_wiki_timeline_numeric_lane.py` for DATE text attribution (`May
  2004`) and count-unit/target recovery (`71 lines of stem cells`).
- Docs/ontology: add a programmatized liability stack crosswalk in
  `docs/ontology.md` that maps compressed System/Norm/Doctrine/Event design
  views back to canonical L0-L6 ontology layers, plus explicit WrongType
  orthogonal dimensions (protected interest, mental state, interference mode,
  duty structure, remedy, defence).
- Data/tests: add `data/ontology/wrong_type_dimensions_seed.yaml` and coverage
  in `tests/test_wrong_type_dimensions_seed.py` to keep wrong-type dimension
  catalogs machine-stable and aligned with `wrong_type_catalog_seed.yaml`.
- Docs/roadmap: extend `docs/roadmaps/DB_ROADMAP.md` Milestone 3 to include
  `InterferenceModeType`, `DutyStructureType`, and `DefenceType` plus the new
  dimension seed catalog deliverable.
- Wikipedia/HCA AAO numeric extraction: suppress date-fragment numerics from
  month+day/date-like spans (including EVENT-labeled `September 11` mentions)
  and slash-date forms (`9/11`) so temporal anchors do not leak into numeric
  lanes.
- Wikipedia/HCA AAO step numeric merge: enforce sentence-allowed numeric-key
  gating when merging `numeric_claims` back into `step.numeric_objects` to
  prevent filtered date fragments from being reintroduced.
- itir-svelte (`wiki-timeline-aoo`): sort numeric lane/context by numeric key
  magnitude (value/unit comparator) instead of lexical label order.
- Docs/TODO: formalize requester coverage UI diagnostics contract under R17
  (`req:none` must surface global/window requester gap counters and missing
  requester event IDs) and split follow-up UI assertions into a dedicated TODO.
- Docs/TODO: extend R18/source modeling contract to require AAO-all Source/Lens
  non-role lanes (context-edge overlays), and track follow-up lane assertion
  tests as explicit TODOs.
- NLP/AAO: add parser-agnostic mapping module `src/nlp/ontology_mapping.py` and
  wire extractor action morphology emission through canonical enums
  (`tense/aspect/verb_form/voice/mood/modality`) with deterministic `unknown`
  fallbacks (R24 baseline implementation).
- Wikipedia/HCA AAO numeric keys: stop emitting composite scale-currency units
  (e.g. `trillion_usd`) and normalize currency-scaled values to scientific form
  keys instead (e.g. `$5.6trillion` -> `5.6e12|usd`), while keeping plain
  currency values unchanged (`$500,000` -> `500000|usd`).
- Wikipedia/HCA AAO numeric mention pass: fix parser-doc token scans for split
  currency compact forms (`$` + `5.6trillion`) and dedupe event numeric objects
  to prefer currency-bearing variants over scale-only duplicates.
- Wikipedia/HCA AAO numeric claims: add explicit semantic-expression and
  surface-phenotype substructures under `numeric_claims[].normalized`
  (`expression` + `surface`) so canonical magnitude identity stays separate from
  scale-word semantics and formatting metadata.
- Numeric ontology: align `Magnitude.id` formatting with the numeric
  representation contract so scientific values remain scientific in identity
  strings (e.g. `mag:5.6e12|usd`, not `mag:5600000000000|usd`).
- itir-svelte (`wiki-timeline-aoo-all`): replace misleading requester placeholder
  node `req:none` with `req:missing` (diagnostics-only) and render requester lane
  only when requesters or missing-requester diagnostics exist.
- itir-svelte (GraphViewport/LayeredGraph): fix SVG sizing so SSR/client renders
  don’t collapse height, and increase default lane spacing (col gaps) to reduce
  lane overlap in dense timeline graphs.
- Wikipedia/HCA AAO subjects/actors: normalize leading definite articles in
  subject identity labels (`the X` -> `X`) so graph subject lanes coalesce
  deterministically (e.g., `the United States` -> `United States`).
- Wikipedia/HCA AAO: add top-level `requester_coverage` diagnostics in artifact
  output to flag request-clause events that still resolve with no requester lane
  actor (`request_signal_events`, `requester_events`, `missing_requester_event_ids`).
- Docs: add canonical v2 requirements register
  (`docs/wiki_timeline_requirements_v2_20260213.md`) and align requirement IDs/status
  for extraction, ontology, attribution, conflict logic, anchor graduation, and validation.
- Docs: mark `docs/wiki_timeline_requirements_v2_20260213.md` as the active
  tracker and keep `docs/wiki_timeline_requirements_698e95ec_20260213.md` as
  provenance/history mapping.
- Wikipedia/HCA AAO: add claim-bearing classification tags
  (`step.claim_bearing`, `step.claim_modality`, `step.claim_id`, and event-level
  `claim_bearing`/`claim_step_indices`) using profile-driven epistemic verbs.
- NLP/AAO: add `src/nlp/epistemic_classifier.py` (predicate typing:
  eventive/epistemic/normative/procedural/unknown) and switch claim-bearing
  tagging to dependency-first classification with profile lexical fallback
  instead of extractor-hardcoded epistemic verb defaults.
- Tests: add deterministic classifier coverage in
  `tests/test_epistemic_classifier.py` and update claim-bearing tests for the
  new classifier-integrated annotation path.
- Wikipedia/HCA AAO: add baseline attribution attachments for claim-bearing steps
  (`event.attributions`) with deterministic direct vs reported attribution typing
  and stable attribution IDs.
- Wikipedia/HCA AAO: emit top-level provenance objects
  (`source_entity`, `extraction_record`) derived from timeline snapshot metadata
  for sourcing-layer integration.
- Wikipedia/HCA AAO numeric claims: enrich `numeric_claims` with structured
  normalization payload (`normalized.value/unit/scale/currency/magnitude_id`)
  and explicit date attribution (`time_anchor` + inline `time_years`) so
  timeline rows retain both canonical numeric identity and temporal context.
- Wikipedia/HCA AAO requester extraction: canonicalize requester possessive/title
  surfaces (e.g. `President Obama's`), resolve via alias map to stable actor IDs,
  and add deterministic fallback from `request` steps when possessor extraction
  is missing to prevent requester-lane collapse.
- Tests: extend claim/attribution coverage with requester normalization,
  requester alias resolution, and request-step fallback checks.
- Tests: add claim-bearing/attribution extractor coverage in
  `tests/test_wiki_timeline_claim_attribution.py`.
- Docs: add robust-context thread requirements register
  (`docs/wiki_timeline_requirements_698e95ec_20260213.md`) with implemented vs
  pending traceability across extractor, UI, and ontology integration tasks.
- Docs: expand robust-context requirement coverage in the same register to
  include identity/non-coercion invariants, claim-bearing classification,
  quantified conflict tri-state, anchor graduation, typed edge basis metadata,
  numeric semantic role typing, and explicit non-goals (`R15..R27`).
- Docs: add sourcing/attribution ontology spec
  (`docs/sourcing_attribution_ontology_20260213.md`) and extend requirements
  register with sourcing/attribution requirements (`R28..R29`).
- Docs: add explicit 10-point architecture gap-closure matrix to
  `docs/wiki_timeline_requirements_698e95ec_20260213.md` mapping each review
  concern to requirement IDs and current status.
- Models/tests: add sourcing/attribution model scaffold
  (`src/models/attribution_claims.py`) with deterministic id helpers, chain-cycle
  validation, graph edge projection helpers, and coverage in
  `tests/test_attribution_claims.py`.
- Wikipedia/HCA AAO: add step-scoped `numeric_claims` with parser-first
  governing-verb alignment and baseline numeric role typing
  (`transaction_price`, `personal_investment`, `revenue`, `cost`, `rate`,
  `count`, `percentage_of`) to prevent multi-verb numeric flattening.
- Tests: extend numeric-lane coverage for numeric role inference and multi-verb
  alignment stress case (`arranged ... for $89 million` vs `invested $500,000`).
- Docs: extend numeric contract with step-scoped NumericRole guidance and
  minimum role taxonomy for multi-verb alignment.
- Wikipedia/HCA AAO numeric normalization: preserve currency prefixes/symbols
  (`$`, `US$`, `A$`, `€`, `£`) in canonical numeric keys, with scale folded into
  scientific value form when currency is explicit (e.g., `$5.6trillion` -> `5.6e12|usd`).
- Tests: extend numeric-lane coverage for currency-bearing mentions and keys
  (e.g., `$500,000` and `$5.6trillion`).
- Wikipedia timeline extraction: add deterministic special-event mention anchors
  for `September 11 attacks` / `9/11` prose mentions without explicit year,
  emitting `2001-09-11` mention anchors without creating synthetic narrative text.
- Wikipedia/HCA AAO: add dedicated `numeric_objects` lane at step/event level
  so numeric quantities (e.g., `89 percent`, `7.2%`) are separated from entity
  and modifier lanes.
- Wikipedia/HCA AAO: add deterministic numeric second pass over sentence text
  to recover numeric mentions that are not promoted via dependency object lanes.
- Ingest (HCA fact timeline): include `numeric_objects` in synthesized
  `timeline_facts[]` rows so chronology views can inspect quantitative facts
  separately from entity objects.
- Tests: add `test_wiki_timeline_numeric_lane.py` for numeric lane/admissibility
  coverage.
- Wikipedia timeline extraction: add inline `kind=mention` anchor extraction for
  embedded month/day/year references inside sentences (e.g., anniversary lines
  mentioning `September 11, 2001`) so month buckets capture referenced events
  without inventing synthetic prose entries.
- Wikipedia AAO fallback hardening: stop promoting generic `-ing` tokens as
  actions in text-only fallback (prevents nominal phrases like `turning point`
  from becoming actions), and tighten spaCy fallback to prefer clause-head
  finite/root verbs over arbitrary participles.
- Wikipedia timeline extraction: add conservative section-heading date-anchor fallback
  for first prose sentence when sentence-local anchors are absent (example:
  `September 11, 2001 attacks` now yields a weak `2001-09-11` event anchor),
  plus media-caption filtering so `thumb|...` lines are not emitted as events.
- Tests: add heading-anchor/media-caption coverage in
  `test_wiki_timeline_extract_section_anchor.py`.
- Docs/planning: add architecture addenda bundle beyond `WrongType` covering
  epistemic layering terminology, graph neutrality/rendering contracts,
  frame-scope projection validation, and evidence/attribution frame typing:
  `architecture_addenda_index_20260212.md`,
  `epistemic_layering_structural_interpretation_20260212.md`,
  `graph_epistemic_neutrality_contract_20260212.md`,
  `frame_scope_projection_validator_20260212.md`,
  `evidence_attribution_frame_contract_v2_20260212.md`.
- Wikipedia/HCA AAO coalescing: tighten deterministic object/step coalescing by
  (a) adding identity-aware object keys from exact resolver hints, (b) making
  step dedupe keys order-insensitive for subject/object sets, and (c) preferring
  canonical entity labels from exact hint titles to reduce alias echo nodes
  (`Bush` vs `George W. Bush`) in truth-lane outputs.
- Tests: add `test_wiki_timeline_coalescing.py` covering identity-key merges,
  canonical entity label preference, and order-insensitive step dedupe keys.
- Wikipedia/HCA AAO: canonicalize event/step actions to lemma-first output
  keys (e.g. `reported` -> `report`) and preserve inflection metadata in
  `action_meta` (`surface`, `tense`, `aspect`, `verb_form`, `voice`) with
  optional `action_surface` for display/replay.
- Tests/guardrails: add `test_wiki_timeline_no_semantic_regex_regressions.py`
  to prevent reintroducing `REPORTED_SUBJECT_RE`-style semantic regex subject
  injection and `reported/cautioned` sentence-family regex branches in the
  wiki timeline AAO extractor.
- Docs: add deterministic Evidence Promotion Contract draft
  (`docs/planning/evidence_promotion_contract_20260212.md`) to formalize
  truth-vs-view boundaries for evidence overlays.
- Wikipedia/HCA AAO: add dependency-based modal-container promotion
  (`have/be` + `xcomp`) so constructions like "had a tendency/opportunity to X"
  emit `X` as the step action and store the wrapper as a modifier instead of
  treating `have` as the primary action.
- Wikipedia/HCA AAO: strengthen parser fallback action selection to prefer
  non-wrapper verbs (`xcomp/ccomp/acl/...`) over `have/be` when available in
  the same sentence.
- Ingest (HCA fact timeline): prefer step `entity_objects` over raw `objects`
  when synthesizing `timeline_facts[]`, while preserving `modifier_objects`
  separately for optional view-layer diagnostics.
- Wikipedia: harden AAO object canonicalization so determiner variants (`the X`
  vs `X`) de-duplicate deterministically with resolver-aware preference; non-link
  object rows now merge hints instead of creating echo nodes.
- Wikipedia: make derived purpose-step extraction verb-gated (spaCy structure
  first, conservative fallback) so non-verbal heads like `for` are not emitted
  as actions.
- Wikipedia: add explicit `entity_objects` and `modifier_objects` lanes to AAO
  steps/events so view layers can hide clause mechanics by default without
  deleting truth-layer extraction artifacts.
- Ingest: citation/sl-reference follow hints in HCA demo lanes now include
  `austlii` and `jade` providers (in addition to wiki/source-document lanes),
  so review workflows can surface legal-source follow targets directly.
- Ingest: source-pack pull/follow scripts now enforce explicit per-host
  request pacing with conservative defaults (`legal_rps=0.25`, `wiki_rps=1.0`,
  `default_rps=0.5`) and record the policy in emitted manifests.
- Ingest: wiki snapshot pull now supports explicit wiki API pacing
  (`--wiki-rps`, default `1.0`) so category traversal stays bounded and polite.
- Ingest (HCA narrative): temporal anchor extraction now supplements spaCy
  DATE entities with cue-qualified bare year tokens (e.g. "since at least
  1954"), so multi-year legal sentences can emit multiple timeline facts.
- Docs: publish S7–S9 roadmaps (span authority, cross-doc topology, read-only UI).
- Docs: add human tools integration guidance + multi-modal system doctrine.
- Docs: update span-signal/promotion/IR invariants to require revision-scoped spans.
- Docs: add timeline ribbon conserved-allocation model and UI invariants.
- Docs: add ITIR ribbon module references + UI selector contract + lens DSL.
- TextSpan: add canonical `TextSpan(revision_id, start_char, end_char)` model.
- Storage: persist TextSpan for rule atoms/elements (span_start/span_end/span_source).
- Ingestion: attach TextSpan to new rule atoms/elements; hard-error on missing spans.
- Cross-doc: upgrade topology schema to `obligation.crossdoc.v2` with `repeals/modifies/references/cites`.
- UI: add read-only Obligations tab with span inspector + fixtures.
- Tests: update cross-doc snapshots + add TextSpan attachment test.
- Docs: add lawyer/psychologist user stories and link from README.
- Docs: extend user stories with additional roles (banker/CEO/manager/etc.).
- Docs: add organization-level user story layer (teams/admins/regulators).
- Docs: add public sector user stories (police/EMS/health/government guardrails).
- Docs: add modern org stack user stories (dev/team/CEO/finance).
- Docs: add air-gapped/battlefield/interop user story layer.
- Docs: add "Against Victor's Memory" doctrine to multimodal system notes.
- Docs: add panopticon refusal manifesto.
- Docs: add state power/structural violence note to panopticon refusal.
- Docs: add activist coordination user story layer.
- Docs: add trauma/authoritarian pressure user story layer.
- Docs: add access-scope and legal reconstruction user story layer.
- Docs: add judicial-context user story layer (judges/staff/bailiffs/family).
- Docs: add public-figure user story (Zohran Mamdani context collapse).
- Docs: add lexeme layer contract + tokenizer/corpus updates.
- Schema: add timeline ribbon JSON schema (draft-07) for conserved allocation spine.
- Docs: add media ethics UI guidelines + hostile cross-exam script.
- Docs: document ingest db-path default + compression stats.
- Text: add lexeme normalizer + compression stats helper.
- Ingest: compute compression stats at PDF ingest.
- CLI: add --db-path to pdf_ingest.
- Tests: add compression stats and lexeme normalizer coverage.
- Tests: verify ingest-time compression stats persisted and recomputable.
- Storage: add lexeme/phrase tables to versioned store schema.
- Ingestion: persist lexeme occurrences per revision (span-anchored).
- Tests: add lexeme occurrence span anchoring coverage.
- Tests: add timeline ribbon conservation property tests.
- Tests: add ribbon UI conservation Playwright spec (gated by `RIBBON_DEMO_URL`).
- Ribbon: add lens DSL evaluator + phase-regime lens packs scaffold.
- Ribbon: add Streamlit ribbon demo tab with selector contract output.
- Ribbon: add ribbon compute helper for segment mass/width normalization.
- Ingest: add `--context-overlays` option to persist context_fields alongside PDFs.
- DBpedia: add curation-time lookup helpers (Lookup API + SPARQL) and query docs.
- DBpedia: allow Lookup API helper to emit a curated external-refs batch skeleton (`--emit-batch`) compatible with `ontology external-refs-upsert`.
- Ontology: add CLI command `ontology external-refs-upsert` to load curated `actor_external_refs` / `concept_external_refs` batches into SQLite.
- DB: make SQLite migration runner idempotent by tracking applied migrations in `schema_migrations` (prevents re-running transitional migrations like legal_system normalization).
- Graph: preserve DBpedia URI-form external IDs in `owl:sameAs`/`skos:exactMatch` exports; canonicalize Wikidata Q-IDs to `wikidata:Q...`.
- DBpedia: fix Lookup API helper so `--emit-batch` works on cache hits (curation workflow no longer depends on a fresh network fetch).
- Wikipedia: add MediaWiki API pull helper to snapshot wikitext + provenance + capped category traversal into gitignored caches.
- Wikipedia: emit per-title progress to stderr during pulls and include environment sanity metadata (`python`, `driver_requested`, `drivers_used`) in stdout JSON.
- Wikipedia: add candidate extraction + distribution report + bounded DBpedia lookup-queue generators (all curation-time; gitignored outputs).
- Wikipedia: add Graphviz renderer for the raw candidate graph (pre-trim sanity) and a DBpedia queue runner (cache-first; optional network) for batch identity glue.
- Wikipedia: add timeline candidate extractor from revision-locked wikitext snapshots (date-anchored, section-aware, non-authoritative).
- Wikipedia: add sentence-local actor/action/object expansion over timeline candidates (heuristic, labeled, non-causal) for curation-time visualization.
- Wikipedia: fix timeline sentence splitting to avoid truncation at common abbreviations (e.g. `U.S.`), and normalize separator templates (e.g. `{{snd}}`) before stripping wikitext.
- Wikipedia: harden AAO extraction to (a) recognize `gave birth`, (b) avoid misclassifying `"to <noun phrase>"` as purpose, and (c) suppress root-surname mapping when the surname is part of a two-token name (e.g. `Laura Bush`).
- Wikipedia: add OAC `span_candidates` lane as **unresolved mentions only** (exclude resolved-entity overlaps + time-only NPs), with optional `hygiene.view_score` for view-layer sorting (truth != view).
- Wikipedia: make AAO purpose extraction dependency-gated via pinned spaCy (infinitival `"to" -> VERB` only; no verb allowlist) and attach extracted purpose to the last step by default when multi-step output is present.
- Wikipedia: add deterministic spaCy fallback action selection when explicit verb patterns miss (`fallback_action_spacy` warning).
- Wikipedia: strip citation-style sentence tails in timeline extraction (e.g. `..., Bush, George W.` and `... . Rutenberg, Jim (...)`) before anchor parsing to avoid polluted event text and downstream span noise.
- Wikipedia: protect middle-initial abbreviations during sentence splitting (e.g. `George W. Bush`) to avoid truncating timeline events into citation-like fragments.
- Wikipedia: improve AAO coverage for `reported ... but cautioned ...` prose by adding split-step extraction (`reported`/`cautioned`/`weakening`), broader verb patterns, and sentence-local surface objects (e.g. `the war`) when unlinked but load-bearing.
- Wikipedia: refine AAO step subjects using deterministic dependency attachments to reduce false co-subjects from object mentions (e.g. birth/vote sentences).
- Wikipedia: emit minimal `chains[]` metadata for multi-step AAO events and add derived purpose-steps when a purpose clause is present but not already represented as a step.
- Wikipedia: harden person-title guardrails (`alliance`, `forces`, `troops`, etc.) and extend action coverage (`initiated`, `discharged`, `suspended`, `told`, `voted`).
- Wikipedia: add dependency-object fallback extraction for unlinked object phrases and emit per-object resolver hints (`exact`/`near`) against sentence links, paragraph links, and candidate-title rows.
- Wikipedia: normalize request-clause AAO extraction so `at ... request` yields requester-led steps (`action=request`) with role-correct subjects/objects instead of leaking request actions onto the main actors.
- Wikipedia: add negation-aware action labels (`not_*`) and clause-link chain kinds (`content_clause`, `infinitive_clause`) for complement structures (e.g. `told` -> `not_voted`).
- Wikipedia: stabilize AAO action vocabulary by storing negation as structured metadata (`step.negation`) while keeping canonical base actions; `not_*` is now a view concern.
- Wikipedia: add profile-driven extraction config (`--profile`) with pinned output provenance (`extraction_profile`) for action regex inventory and requester title labels.
- Wikipedia: refine subject-surface extraction for conjunctions so dependency subjects preserve both actors in coordinated subjects (`Bush and Bill Clinton`) without collapsing to one.
- Ontology: add a small curation helper to upsert a minimal `actors(kind,label)` row into an ontology SQLite DB.
- Ingest: add `hca_case_demo_ingest.py` link-selection scoring so multi-link rows resolve to the intended artifact (e.g., judgment summary PDF vs judgment HTML page).
- Ingest: add HCA recording transcript/caption hardening with AV transcript fallback, Vimeo `config/request` fallback, and HLS/DASH manifest capture for no-progressive streams.
- Ingest: extend HCA AAO output to emit explicit signal lanes (`artifact_status`, `recording_artifact`, `narrative_sentence`) and merge sentence-local narrative AAO extracted from ingested PDF text.
- Ingest: add SB observer-signal payload export for HCA demo bundles (`sb_signals.json`) so adapter events can be consumed by SB without asserting normative truth.
- Ingest: shift HCA narrative sentence gating to parser-first (spaCy token/POS checks) and reserve regex for worst-case fallback splitting/hygiene only.
- Ingest: add narrative citation extraction for HCA sentence events (`citations[]`) with follower hints ordered as `wikipedia -> wiki_connector -> source_document -> source_pdf`; citation-like object noise is filtered from AAO object lists.
- Ingest: add parser-native narrative `sl_references[]` lane for HCA events by joining source `document_json` references (`provisions`, `rule_tokens`, `rule_atoms`) back onto sentence-level events with provenance fields (`source_document_json`, `provision_stable_id`, `rule_atom_stable_id`).
- Ingest: propagate `sl_references[]` into `sb_signals.json` and include `wiki_connector` follow hints (`wiki_pull_api.py`, preferred `pywikibot`) alongside existing citation follower hints.
- Ingest: enrich HCA narrative events with `party`, `toc_context[]`, `legal_section_markers`, and `timeline_facts[]` (DATE-entity anchored, deterministic) and emit top-level `fact_timeline[]` for linear chronology views over out-of-order prose.
- Ingest: move HCA `party` attribution to parser-first document-structure inference (`toc_entries`, metadata, sentence token cues), with explicit `party_source`/`party_evidence`/`party_scores` and label fallback only when unresolved.
- Ingest: add bounded source-pack puller (`scripts/source_pack_manifest_pull.py`) that fetches explicit `seed_urls` only and emits deterministic `manifest.json`, `timeline.json`, and `timeline_graph.json` artifacts for legal-principles bootstrap workflows.
- Ingest: add bounded authority-link follow pass (`scripts/source_pack_authority_follow.py`) with explicit depth/doc caps (`max_depth`, `max_new_docs`) and deterministic follow artifacts (`follow_manifest.json`, `follow_timeline.json`, `follow_timeline_graph.json`).
- Ingest (HCA timeline facts): split chronology-table sentence rows into date-scoped chunks before AAO extraction, suppress redundant year-only anchors when a stronger same-year month/day anchor exists, and filter citation/date noise from `timeline_facts[].objects` to reduce circular-looking fact fan-out.
- Wikipedia AAO: de-noise parser input by stripping parenthetical citation tails before dependency extraction; keeps canonical event text unchanged while reducing `CAB/SC/...` leakage into extracted actions/objects/purpose.
- Wikipedia AAO: normalize possessive evidence subjects to person actors (`X's evidence` -> `X`) and apply shared entity-surface cleanup for footnote/citation tails in subject/object lanes.
- Wikipedia AAO: promote person/party-role dep objects (`Fr ...`, `Mr ...`, `the appellant/respondent`) into `entity_objects` when unresolved, so legal-narrative actor visibility survives without ID-only gating.
- Wikipedia AAO: replace hardcoded `reported/cautioned` sentence-family split + `REPORTED_SUBJECT_RE` injection with profile-driven dependency communication chains (`communication_verbs` + `ccomp/xcomp` embedded steps + attribution modifiers).
- Wikipedia AAO: suppress numeric day/year fragments inside month+digit date phrases (token-pattern date spans) so `September 11` no longer leaks `11` into `numeric_objects`.
- Wikipedia AAO: numeric extraction now prefers spaCy span candidates (with dependency-derived units) over raw entity/token scans; fixes cases like `71 ... "lines"` -> `71 lines` in numeric lane.
- Wikipedia AAO: requester lane now tags request targets from dependency structure for request-signal verbs with infinitival complements (e.g., `urged Congress to ...` -> requester=`Congress`).
- Wikipedia AAO: actor surface cleanup strips a single leading `the` token (`the United States` -> `United States`) for deterministic coalescing hygiene.
- Wikipedia AAO: preserve timeline-row `url`/`path` metadata as `citations[]` follow hints (`provider=source_document`) for source-pack ingestion datasets.
- Docs: add dedicated wiki timeline actor/subject coalescing contract (`docs/actor_coalescing_contract.md`).
- Docs: add wiki timeline storage contract clarifying JSON exports vs canonical DB persistence (`docs/wiki_timeline_storage_contract.md`).
- Wikipedia AAO: persist AAO run/event payloads into a canonical SQLite store (default `--db-path` to `SensibLaw/.cache_local/wiki_timeline_aoo.sqlite`, disable via `--no-db`), with deterministic `run_id` and idempotent `(run_id,event_id)` writes.
- UI (AAO-all): source lane labels now include per-row source titles (`source_row:*`) and follow URL hosts (`host:*`) so source-pack timelines show their underlying pages.
- Docs: add descriptive-only judicial decision outcome distribution contract (`docs/judicial_decision_behavior_contract.md`) with individual-level disabled-by-default guardrails.
- Core: add `src/judicial_behavior` descriptive aggregation module (deterministic, non-predictive; judge grouping requires explicit opt-in).
- Judicial behavior (descriptive-only): require explicit slice declarations for
  aggregations, and always emit corpus disclosure metadata (`n_total`, observed
  time bounds) plus a mandatory statistical interpretation guard string.
- Judicial behavior (descriptive-only): ridge-logistic MAP association and lognormal tail helpers now expose contracted aggregation APIs that enforce the same slice+disclosure invariants as counts/Beta/Gamma.
- Docs: add descriptive-only official decision behavior contract (`docs/official_decision_behavior_contract.md`).
- Core: add `src/official_behavior` descriptive aggregation module (deterministic, slice-declared, individual-level disabled by default) for commitment↔action alignment summaries.
- Docs: add Iraq-slice official feature schema (`docs/official_behavior_feature_schema_us_exec_foreign_policy_iraq_v1.md`) and a cross-domain projection contract (`docs/decision_observation_projection_contract.md`).
- Core: add projection-only `DecisionObservation` view (`src/behavior_projection`) and minimal `ActionObservation` record type (`src/official_behavior/action_model.py`) to share descriptive aggregation plumbing without replacing domain models.
- Tests: add regression coverage to enforce individual-level stats are disabled by default.
- Core: add deterministic Beta-Binomial posterior estimation with empirical-Bayes priors for descriptive rate estimation (theta mean + credible interval; no sampling; individual grouping remains opt-in).
- Tokenizer/Storage: normalize leading determiners for canonical `act_ref` /
  `instrument_ref` collapse (`the ...` no longer splits equivalent atoms).
- Storage: extend structural atom dictionary persistence to include
  `article_ref` and `instrument_ref`, and persist the same high-yield atom
  dictionary/occurrence rows in the root wiki-timeline SQLite store.
- Ontology bridge: add end-to-end regression coverage for
  `emit_bridge_external_refs_batch.py` feeding the existing
  `ontology external-refs-upsert` CLI path into `actor_external_refs`.
- Ontology bridge: move bridge resolution onto a DB-backed deterministic
  substrate in `itir.sqlite` (`wikidata_bridge_slices`, `wikidata_bridge_entities`,
  `wikidata_bridge_aliases`, `wikidata_bridge_match_receipts`) with a seeded
  reviewed v1 body/court slice.
- CLI: add `ontology bridge-import` and `ontology bridge-report` for deterministic
  bridge-slice management on the shared DB.
- Storage reporting: extend `wiki_timeline_storage_report.py` to include
  structural-atom duplication estimates plus duplicated external-ref URL/note
  bytes and bridge-slice storage stats.
- Tokenizer/bridge scope: add first GWB-oriented U.S. body aliases
  (`U.S. Senate`, `House of Representatives`, `CIA`, `FBI`, `Department of Defense`)
  while keeping QID resolution deterministic and slice-backed.
- Data: add checked-in reviewed bridge slice
  `SensibLaw/data/ontology/wikidata_bridge_bodies_gwb_v1.json` and import it
  into the live `itir.sqlite` bridge substrate.
- Ops: live `itir.sqlite` wiki timeline runs were repersisted through the new
  normalized event/atom path (`14` runs) so storage reports now include
  structural-atom stats on existing GWB timeline runs.
- Storage: remove remaining canonical wiki-timeline JSON-bearing list/tail
  persistence in favor of typed path/value tables for event fields, step
  fields, object resolver hints, event list items, and run list items. Legacy
  blob columns remain only as compatibility columns and now report `0`
  residual bytes on the refreshed GWB storage run.
- Storage: fix `persist_wiki_timeline_aoo_run` parent-run writes to use
  conflict updates instead of `INSERT OR REPLACE`, and clear legacy
  `wiki_timeline_event_lists` / `wiki_timeline_run_lists` rows during
  repersist so eager rewrite on `itir.sqlite` succeeds under foreign keys.
- Ops: rerun the eager rewrite into `.cache_local/itir.sqlite` after the
  zero-residual storage patch; the live canonical root DB again reports all
  required wiki timeline suffixes present.
- Storage reporting: refreshed live GWB storage report now shows
  `normalized_bytes_estimate=139476`, `bytes_per_event_normalized_estimate≈982`,
  and `residual_blob_bytes=0` for
  `run:ecb0dbdaac1f05137c9f88e5be5f552a3d3e992967b6a078ac1410587f10f3dc`.
- Chat ingest: add `SensibLaw/scripts/ingest_chat_sample_to_itir_test_db.py`
  for bounded local chat-sample ingestion into an isolated test DB with hashed
  thread IDs only; canonical `itir.sqlite` is backed up first and chat data
  stays out of the live shared DB.
- Docs: tighten the wiki timeline storage contract so canonical DB persistence
  is judged by typed route/query/report semantics, not by lossless retention of
  arbitrary legacy JSON export tails.
- Storage: stop writing step `action_meta_json` into compatibility blob columns
  on fresh persists; typed `wiki_timeline_step_field_values` is now the only
  canonical path for that data.
- Tests: add `test_wiki_timeline_storage_report.py` so fresh persists must
  report `residual_blob_bytes = 0`, and rerun the targeted wiki timeline
  storage/parity/migration subset successfully.
- Metrics: record isolated chat-sample tokenizer/compression smoke results
  (`100` messages, `465653` raw chars, `104974` tokens, `4.4359` chars/token,
  reuse ratio `0.9317`, `52` structural tokens) alongside the existing
  deterministic GWB/legal corpus comparison points.
- Docs/TODO: add a concrete GWB U.S.-law linkage seed plan and clarify that
  chat-sample structure reporting must include kind breakdowns beyond `_ref`
  counts when evaluating prose-heavy corpora.
- Ontology bridge: extend the reviewed GWB body/court slice with
  `Department of Defense` (`Q11209`) and the `United States Court of Appeals
  for the Sixth Circuit` (`Q250472`); live bridge import now reports `12`
  entities / `49` aliases.
- Chat ingest: harden the isolated chat test schema with explicit
  `source_namespace`, `source_class`, `retention_policy`, and
  `redaction_policy`, and persist structural-atom dictionary/occurrence tables
  in `.cache_local/itir_chat_test.sqlite`.
- Metrics: add `scripts/report_chat_test_tokenizer_stats.py` so isolated chat
  samples now report full token-kind breakdowns, structural-kind breakdowns,
  top structural atoms, and dedupe counts instead of only aggregate `_ref`
  totals.
- Data: add deterministic starter pack
  `SensibLaw/data/ontology/gwb_us_law_linkage_seed_v1.json` for GWB U.S.-law
  linkage work.
- Added a second deterministic operational/discourse structure lane for chat, shell, context, and transcript-style corpora.
- Added `report_structure_corpora.py` plus richer chat structure reporting with top atoms, usefulness scores, co-occurrence/interlink summaries, and bounded example snippets.
- Isolated chat sample ingest now persists operational/discourse `_ref` occurrences alongside legal refs via the existing atom tables.
- Tightened the operational/discourse lane to avoid date-like and all-caps slash false positives, and added WhatsApp-style transcript turn detection for speaker/timestamp lines.
- Collapsed duplicate WhatsApp-style transcript timestamps to a single canonical timestamp atom per line and added side-by-side per-source corpus comparison reporting.
## 2026-03-26

- Wikidata disjointness lane: formalized the current live-first discovery
  posture after local `zelph` scans showed no useful contradiction signal from
  either retained pruned Wikidata bin.
- Ops/docs: recorded that `wikidata-20171227-pruned.bin` (`~1.4 GiB`) and
  `wikidata-20260309-all-pruned.bin` (`~5.6 GiB`) are still retained locally
  for runtime/loader repro and negative-control use, not as practical
  contradiction-source artifacts.
- Evidence: baseline profile, wide profile, bounded profile, exact-QID
  presence checks, and a seedless contradiction scan on the newer pruned bin
  all returned zero useful local signal for the current target families.
- Planning: added a follow-up question for the Zelph developer about whether
  the Wikidata `.bin` format can support sharding or remote/range-readable
  access without full local materialization.

## 2026-03-07

- added `au_semantic` reviewed seed import/report lane mirroring the current
  GWB linkage pattern for the Australian proving corpus
- added `au_semantic` deterministic semantic pipeline on the frozen v1.1 shape:
  document-local non-famous participants, abstention on weak forum labels, and
  edge-first relation candidates/promotions
- added focused Australian tests covering:
  - reviewed seed import + matching
  - document-local actor creation
  - abstention on `the Court`
  - promoted appeal/review relations without schema changes
# 2026-03-27
- Parser-basis refinement for covered semantic relation lanes:
  - Tightened GWB/transcript relation `semantic_basis` derivation so
    `structural` now requires an explicit subject/object/predicate receipt
    spine, with `mixed` reserved for partial relation structure instead of
    policy/meta receipts.
  - Added explicit transcript relation receipts for `felt_state`
    (`object_state`) and `replied_to` (`predicate`) so those candidate rows
    remain structurally grounded under the stricter basis rule.
  - Added coverage in `tests/test_gwb_semantic.py` and
    `tests/test_transcript_semantic.py` to pin the stricter basis semantics.
- Contested semantic-basis refinement:
  - Tightened `scripts/build_affidavit_coverage_review.py` so explicit
    `predicate_text` / component bindings now count as `structural` basis,
    while lexical justification hints remain the reason a row stays `mixed`.
  - Added focused coverage in `tests/test_affidavit_coverage_review.py` to pin
    the new contested basis boundary.
- Semantic-basis summary instrumentation:
  - Added `summary.semantic_basis_counts` to GWB semantic reports, transcript
    semantic reports, and affidavit-coverage review artifacts so remaining
    `mixed` / `heuristic` basis shrinkage is measurable directly in the output
    surfaces.
  - Added coverage in `tests/test_gwb_semantic.py`,
    `tests/test_transcript_semantic.py`,
    `tests/test_affidavit_coverage_review.py`, and
    `tests/test_google_docs_contested_narrative_review.py`.
- Semantic-promotion gate enforcement:
  - Added `tests/policy/test_semantic_gate_enforcement.py` to assert that the
    currently covered truth-bearing lanes route canonical promotion fields
    through the central promotion gate / claim-state path, and that
    mission-observer overlays remain outside the truth-bearing family.
  - Updated semantic-governance coverage docs/TODO/context to reflect that
    covered-lane static enforcement is now implemented and the remaining next
    gap is deeper parser-backed structural basis in those lanes.
- Story/progress alignment for semantic-promotion follow-through:
  - Updated `docs/user_stories.md` to add explicit semantic-governance /
    promotion-integrity and mission accounting crossover client stories.
  - Updated
    `docs/planning/user_story_implementation_coverage_20260326.md` to record
    the current semantic-governance layer as implemented enough to claim,
    while naming the remaining completeness gaps: repo-wide promotion-gate
    enforcement, deeper parser-backed structural basis, and the still-
    operational mission-observer boundary.
  - Updated `todo.md` and `COMPACTIFIED_CONTEXT.md` so the next-step posture is
    explicit: central promotion-gate CI/static enforcement first, structural-
    basis improvement second, and no mission-observer truth promotion without a
    dedicated SL-reducer-backed model.
- ITIR / SensibLaw PostgreSQL schema and deployment bundle:
  - Added
    `docs/planning/itir_sensiblaw_postgres_schema_and_deployment_bundle_20260328.md`
    as the execution-oriented refinement of the current production pack.
  - Recorded PostgreSQL as the reference production schema while keeping the
    first runtime target local-first and single-user.
  - Made the reference bundle explicit about:
    extensions/enums, dependency-ordered core tables, trigger helpers,
    operational views, dashboard roles, and staged deployment tiers.
  - Tightened the same note with explicit migration ordering plus the bounded
    interface split:
    `/api/v1` REST surface for case/runtime endpoints and local worker-service
    interfaces for processing, identity, graph, alignment, mode, obligation,
    output, and governance.
  - Synced TODO/context so the next bounded implementation artifact is framed
    as migration-ready SQL in execution order or a local service/API spec over
    the same entity set, not a full collaboration-platform rollout.
- Affidavit local-first proving slice:
  - Added `docs/planning/affidavit_local_first_proving_slice_20260329.md` to
    pin affidavit, not tenancy, as the first SQLite/local-first proving slice
    for narrative integrity and evidence structure.
  - Tightened
    `docs/planning/affidavit_coverage_review_lane_20260325.md` so the current
    lane now explicitly includes a bounded grouped proving-slice read model.
  - Added `build_contested_affidavit_proving_slice(...)` in
    `src/fact_intake/read_model.py` plus a `contested-proving-slice` query
    surface in `scripts/query_fact_review.py`.
  - Added focused regression coverage in
    `tests/test_affidavit_coverage_review.py` and
    `tests/test_query_fact_review_script.py`.
  - Verified the new slice with:
    `.venv/bin/python -m pytest -q SensibLaw/tests/test_affidavit_coverage_review.py SensibLaw/tests/test_query_fact_review_script.py`
  - Tightened the proving-slice grouping so explicit response-role and
    support/conflict signals can promote rows into `disputed` or
    `weakly_addressed` without inflating `covered`.
  - On the real Google Docs affidavit/response run, the grouped top-line read
    improved from:
    `supported 1 / missing 28 / needs_clarification 17 / disputed 0`
    to:
    `supported 1 / disputed 7 / weakly_addressed 36 / missing 2`.
  - Added opt-in progress reporting to
    `scripts/build_affidavit_coverage_review.py` and
    `scripts/build_google_docs_contested_narrative_review.py`, so live
    contested Google Docs runs now emit fetch/extract/group/match/write stages
    and per-proposition matching progress instead of appearing stalled.
  - Added opt-in trace reporting to the same affidavit builders so operators
    can stream proposition decomposition and classification events such as:
    proposition start, tokenization, top candidate selection, response packet
    inference, final classification, semantic basis, and promotion result.
  - Added regression coverage for the new progress surfaces in
    `tests/test_affidavit_coverage_review.py` and
    `tests/test_google_docs_contested_narrative_review.py`.
  - Added
    `docs/planning/affidavit_claim_reconciliation_contract_20260329.md` to
    pin the next quality step as relation-driven claim reconciliation rather
    than more similarity-led bucketing.
  - Tightened
    `docs/planning/affidavit_coverage_review_lane_20260325.md` so the current
    matcher is now explicitly described as a bounded `v0` bridge toward a
    typed relation classifier with dominant-relation bucket resolution.
  - Synced `TODO.md` and context so the next affidavit-lane quality work is
    now framed as:
    normalized proposition/response typing -> bounded relation classifier ->
    dominant relation resolution -> final bucket mapping.
  - Tightened the same affidavit planning notes so `weakly_addressed` is now
    explicitly treated as a transitional defect bucket rather than a stable
    target output class.
  - Recorded the next classifier expectation as:
    split mixed `weakly_addressed` rows into `partial_support`,
    `adjacent_event`, `substitution`, and `non_substantive_response`, while
    requiring per-row explanation fields:
    classification, matched response, reason, and missing dimension.
  - Added an explicit cross-lane priority decision:
    affidavit claim reconciliation is now the higher immediate implementation
    priority, while `TEMP_zos_sl_bridge_impl` stays second priority until its
    retrieval path gains an explicit admissibility / acceptance boundary.
  - Implemented the first affidavit claim-reconciliation followthrough in
    `src/fact_intake/read_model.py`:
    the proving slice now emits `relation_root`, `relation_leaf`,
    `explanation`, and `missing_dimensions`, and exposes explicit
    `partial_support` / `adjacent_event` / `substitution` /
    `non_substantive_response` sections instead of a stable
    `weakly_addressed` section.
  - Updated focused regression coverage in
    `tests/test_affidavit_coverage_review.py` and
    `tests/test_query_fact_review_script.py`.
  - Verified with:
    `.venv/bin/python -m pytest -q SensibLaw/tests/test_affidavit_coverage_review.py SensibLaw/tests/test_query_fact_review_script.py`
- Agda boundary docs alignment:
  - Updated `docs/interfaces.md` and
    `docs/plan_qg_unification_sl_da51_agda_contract_20260324.md` so the Agda
    side now explicitly matches the current `CLOCK` / `DASHI` reading: cyclic
    `Z/6 -> Z/3` lift, not dihedral, with cone / contraction / MDL retained as
    the admissibility gate.
  - Updated `todo.md` so any later Agda formalization keeps that reading
    explicit instead of smuggling phase labels into proof or truth authority.
- `2026-03-30` affidavit predicate-family routing pass:
  - stopped dropping adjusted duplicate-root support rows when their raw
    segment overlap was zero
  - tightened sibling-family routing so live Dad/Johl now keeps:
    - `p2-s5` on the audio-control row
    - `p2-s6` on the keyboard-control row
    - `p2-s21` on the EPOA revocation row instead of the nearby August RTA row
  - focused verification:
    `54 passed`
  - live artifact:
    `/tmp/dad_johl_predicate_family_v5/affidavit_coverage_review_v1.json`
- `2026-03-30` affidavit SQLite-first runtime seam:
  - `scripts/build_affidavit_coverage_review.py` now allows persisted
    contested-review runs to skip bulky JSON/markdown review artifacts when
    `write_artifacts = False`
  - `scripts/build_google_docs_contested_narrative_review.py` now accepts
    `--db-path` and defaults to the persisted SQLite receiver when that flag is
    present
  - live Google Docs affidavit review now keeps bulky JSON/markdown artifacts
    as an opt-in presentation/export contract via `--write-artifacts`, not a
    mandatory runtime output
  - added focused regression coverage in:
    - `tests/test_affidavit_coverage_review.py`
    - `tests/test_google_docs_contested_narrative_review.py`
  - focused verification:
    `51 passed in 2.25s`
- `2026-03-30` affidavit Phase 1 milestone 1:
  - added `scripts/query_fact_review.py contested-rows` as a narrow
    SQLite-first inspection surface for persisted contested affidavit runs
  - added focused coverage in `tests/test_query_fact_review_script.py`
  - this gives the Dad/Johl debugging loop direct DB access to:
    relation root/leaf, excerpts, response role, promotion status, explanation,
    and matched-source-row detail without opening the bulky review artifact
