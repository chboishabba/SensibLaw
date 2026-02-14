# TODO

- Milestone (current): **Sprint S9 — Human Interfaces (Read-Only, Trust-First)** — ✅ complete.
- Previous milestone: **Sprint S8 — Cross-Document Norm Topology (Non-Judgmental)** — ✅ complete.
- Active sprint focus: preserve span authority + read-only surfaces; no reasoning creep.

## S7–S9 (current arc)
1) S7 — Span Authority & Provenance Closure (TextSpan contract, Layer 3 enforcement, promotion gate hardening) — ✅ complete
2) S8 — Cross-Document Norm Topology (non-judgmental graph, span-derived edges only) — ✅ complete
3) S9 — Human Interfaces (read-only, trust-first UI with span inspectors and diff views) — ✅ complete

## Epistemic modes (doctrine)
- Define explicit statuses: hypothesis, intention, projection, narrative, evidence, commitment.
- Ensure any UI surfaces show status and never auto-promote.

## Judicial behavior (descriptive-only)
- DONE: Add mandatory slice declaration + sample-size/time-bounds disclosure to the
  judicial behavior aggregation contract and enforce it in output payloads.

## S6 sequencing (completed)
  1) S6.1 Obligation Query API (read-only filters by actor/action/object/scope/lifecycle; respect flags) — ✅ done
  2) S6.2 Explanation & trace surfaces (atoms → spans, deterministic ordering) — ✅ done
  3) S6.3 Cross-version obligation alignment (unchanged/modified/added/removed with metadata deltas) — ✅ done
  4) S6.4 Normative view projections (actor/action/timeline/clause views; deterministic) — ✅ done
  5) S6.5 External consumer contracts (versioned JSON schemas for obligation/explanation/diff/graph) — 🚧 stubs seeded (query, explanation, alignment)
  6) S6.6 Hard stop & gate review (no-reasoning guard doc and red-flag tests) — ✅ done

- S6 guardrails: clause-local, text-derived only; identity/diff invariants frozen; outputs are read-only and deterministic; no invented nodes/edges; no compliance judgments.
- Tests-first rule: add pytest coverage for each sub-sprint before wiring code; feature-flag new surfaces if identity/output risk exists.

- Near-term task focus
- Layer 3 LegalSystem authority-boundary contract (online context `698eba02-3da4-839c-98c7-c9bcf062fa86`)
  - DONE (2026-02-13): docs updated to treat `LegalSystem` as normative authority boundary (sovereignty tier + parent hierarchy), not a country label.
  - DONE (2026-02-13): SQLite migration `004_legal_system_authority_contract.sql` adds authority fields and AU sub-sovereign hierarchy seeds, including constitutional source linkage.
  - DONE (2026-02-13): Postgres/schema parity migrations added (`database/postgres_migrations/005_legal_system_authority_contract.sql`, `schemas/migrations/005_layer1_legal_system_authority_contract.sql`).
  - DONE (2026-02-13): migration tests extended (`tests/test_db_migrations_and_daos.py`) to assert sovereignty tier, parent links, commencement date, and constitutional source IDs.
- Text-method inventory (2026-02-13) — regex usage map + alignment note
  - inventory command:
    - `rg -n "\bre\.(compile|search|match|fullmatch|finditer|findall|sub|split|subn)\(" SensibLaw/scripts SensibLaw/src -S`
  - top regex hotspots (count = direct `re.*` calls):
    - `src/pdf_ingest.py` (86)
    - `scripts/wiki_timeline_aoo_extract.py` (74)
    - `scripts/hca_case_demo_ingest.py` (31)
    - `scripts/wiki_timeline_extract.py` (23)
    - `src/ingestion/hca.py` (19)
    - `src/reliability/pre_brief.py` (18)
  - alignment status against parser-first/value-key split:
    - aligned now (numeric lane):
      - `scripts/wiki_timeline_aoo_extract.py` numeric spans are parser-first (spaCy entity/token), value-keyed via Decimal/Babel (`_numeric_key`), regex fallback only.
    - aligned now (action lane):
      - `scripts/wiki_timeline_aoo_extract.py` action selection is parser-first
        via spaCy token lemma+dependency classification (`src/nlp/event_classifier.py`),
        with regex patterns retained as explicit fallback only.
    - acceptable regex-primary lanes (format parsing, not semantic extraction):
      - HTML/document parsing lanes (`scripts/hca_case_demo_ingest.py`, `src/ingestion/hca.py`, `src/pdf_ingest.py`)
      - citation/date formatting lanes (`scripts/wiki_timeline_extract.py`, citation helpers)
    - remaining semantic regex debt (needs de-hardcoding):
      - `scripts/wiki_timeline_aoo_extract.py` requester/action sentence-family branches (`REQUEST_RE`, `BY_AGENT_RE`, action/surface phrase branches)
      - `scripts/wiki_timeline_aoo_extract.py` legacy surface split heuristics (`joined/commissioned`, `speech/threw`, etc.)
  - next cleanup pass (text-method focused):
    - replace requester/action surface regex branches with dependency/profile rules where possible
    - keep regex only in citation/date/hygiene and explicit fallback lanes with warnings
    - add guard tests for grouped numerics and unit-only noise (done), extend to requester/action de-regex invariants
    - DONE (semantic-resource lane baseline):
      - profile now emits normalized `semantic_backbone` metadata and enforces
        deterministic/non-generative settings (`llm_enabled=false`,
        deterministic `wsd_policy` values only) in extractor runs.
      - canonical extraction path is explicitly non-generative; invalid
        nondeterministic semantic-backbone profile settings fail fast.
    - TODO (semantic-resource lane completion):
      - define/version-pin deterministic WSD policy implementation details for
        future synset-backed canonical action/entity mapping.
      - implement profile-gated deterministic synset mapping pipeline
        (WordNet/BabelNet resource pins + explicit synset action maps +
        fail-fast runtime validation).
      - add mapping-table sha256 pins:
        - `semantic_version_pins.babelnet_table_sha256`
        - `semantic_version_pins.synset_action_map_sha256`
  - AAO extractor de-hardcoding contract (wiki_timeline_aoo_extract.py):
    - origin_online_id: `698bdf6e-43f8-839c-9089-34ee3d3338dd` (documented provenance only; no live fetch)
    - hardcoded now:
      - requester title -> `"U.S. President"` subject injection in request-step normalization
      - static action regex map + sentence-specific split branches
      - static person-token guardrails and title-word blocklists
      - surface phrase object insertion for known prose shapes
      - root actor/surname defaults tied to Bush dataset
    - required to eliminate hardcoding:
      - external office-role mapping (ID-backed) for requester/title expansion
      - profile-driven action/split config (versioned, provenance-emitted)
      - dependency-first clause/frame builder (regex as fallback only)
      - typed entity/object promotion contract to replace surface phrase injections
      - dataset bootstrap manifest for root actor aliases (no hardcoded CLI literals)
      - regression goldset + invariants for request/passive/chain/object scenarios
    - DONE (first step): extractor now loads a versioned external profile (`--profile`) for
      action regex inventory and requester title labels, and emits profile provenance in artifact output.
    - DONE (second step): AAO object dedupe now canonicalizes determiner variants (`the X` vs `X`)
      and prefers resolver-strong rows deterministically; purpose-step generation is verb-gated
      (spaCy parse first, conservative fallback) so non-verbs such as `for` no longer become actions.
    - DONE (fourth step): dependency modal-container promotion now rewrites `have/be` + `xcomp`
      constructions into semantic action heads (e.g. "had a tendency/opportunity to X" -> `X`)
      with wrapper metadata stored as a step modifier.
    - DONE (fallback hardening): parser fallback action chooser now prefers non-wrapper verbs
      in complement/relative lanes over `have/be` when present in the same sentence.
    - DONE (third step): AAO now emits explicit `entity_objects` vs `modifier_objects` lanes at
      both event and step level, keeping truth broad while letting views suppress clause mechanics.
    - DONE (fifth step): HCA fact-timeline synthesis now prefers `entity_objects` for `objects`
      output and keeps `modifier_objects` as a separate field to avoid abstract-mechanics fan-out.
    - DONE (subject/object hygiene): sentence parsing now strips parenthetical citation tails before
      dependency extraction, resolves possessive subject wrappers (`X's evidence`) to person actors,
      and applies shared footnote/citation cleanup so person/party mentions (e.g. `Fr Dillon`,
      `the appellant`) are retained in `entity_objects` rather than lost to modifier-only lanes.
    - DONE (communication chains): replaced sentence-family `reported/cautioned` branch and
      `REPORTED_SUBJECT_RE` subject injection with profile-driven dependency extraction of
      communication/complement chains (`ccomp`/`xcomp`) plus attribution modifiers.
    - DONE (action canonicalization): emit lemma-first `action` keys in event/step outputs and
      preserve surface/morph metadata (`action_meta`: tense/aspect/verb_form/voice, plus optional
      `action_surface`) so dedupe uses canonical actions without losing display detail.
    - DONE (contract): documented deterministic coalescing contract for wiki AAO lanes
      (`docs/planning/wiki_timeline_coalescing_contract_20260212.md`) covering
      entity/action/step/evidence boundaries and forbidden fuzzy/regex merge inputs.
    - DONE (docs bundle): captured broader architectural addenda beyond `WrongType`
      in:
      - `docs/planning/architecture_addenda_index_20260212.md`
      - `docs/planning/epistemic_layering_structural_interpretation_20260212.md`
      - `docs/planning/graph_epistemic_neutrality_contract_20260212.md`
      - `docs/planning/frame_scope_projection_validator_20260212.md`
      - `docs/planning/evidence_attribution_frame_contract_v2_20260212.md`
      - `docs/numeric_representation_contract_20260213.md`
      - `docs/sourcing_attribution_ontology_20260213.md`
      - `docs/wiki_timeline_requirements_v2_20260213.md` (canonical requirements register + status trace)
      - `docs/wiki_timeline_requirements_698e95ec_20260213.md` (thread-provenance trace artifact)
    - DONE (2026-02-14, storage): persist wiki timeline AAO extractor outputs into a canonical SQLite store
      per `docs/wiki_timeline_storage_contract.md` (JSON remains a rebuildable export artifact).
      Added `--db-path` (default) + `--no-db`, deterministic `run_id` (timeline hash + profile hash + parser signature),
      idempotent `(run_id, event_id)` writes, and minimal indexing on anchor year/month/day.
    - DONE (CI guard): add regression test that blocks reintroduction of semantic regex shortcuts
      for reported/cautioned subject/action inference in `wiki_timeline_aoo_extract.py`;
      keep regex usage limited to citation/date/hygiene parsing lanes.
    - DONE (coalescing hardening): step dedupe now uses normalized set semantics
      (order-insensitive subject/object identity) with identity-aware object keys
      sourced from exact resolver hints; cross-frame projection guardrails remain
      pending in the timeline scope validator task.
    - TODO (scope validator): add projection invariant checks for frame-scoped timeline rows
      (`entity_participation`/frame lineage) to catch "date -> action -> everything"
      fan-out regressions during ingest/view synthesis.
    - TODO (UI neutrality pass): implement explicit node/edge class rendering contract
      from `graph_epistemic_neutrality_contract_20260212.md` (modifier lane styling,
      evidence overlay styling, and scope/profile badges).
    - TODO (frame typing): add explicit frame classes (`PROPOSITION`, `ASSERTION`,
      `EVIDENCE`, `REASONING`) and typed edge-basis metadata during extraction and
      graph payload emission per `evidence_attribution_frame_contract_v2_20260212.md`.
    - TODO (adapter reliability): add an explicit `--offline-from-local` mode to
      `hca_case_demo_ingest.py` so network/DNS failure cannot collapse manifest URLs or produce
      shallow artifact-only payloads when local `raw/` + `ingest/*.document.json` already exist.
    - DONE (timeline circularity guard): HCA ingest now pre-splits chronology-table rows into
      date-scoped sentence chunks, de-duplicates same-year weaker anchors (`YYYY` dropped when
      `YYYY-MM`/`YYYY-MM-DD` exists), and strips citation/date noise from `timeline_facts` objects.
    - DONE (wiki timeline heading-anchor fallback): `wiki_timeline_extract.py` now supports
      conservative section-heading date anchors (e.g., `September 11, 2001 attacks`) for the
      first prose sentence when sentence-local anchors are absent; media-caption lines are skipped.
    - DONE (inline mention anchors): timeline extraction now emits additional weak
      `kind=mention` anchors for embedded month/day/year mentions within a sentence
      (e.g., `September 11, 2001`), without synthesizing new prose rows.
    - DONE (special event mention anchors): timeline extraction now also captures
      deterministic `September 11 attacks` / `9/11` references without explicit
      year as `2001-09-11` mention anchors (frame-scoped, non-causal).
    - DONE (AAO fallback cleanup): text fallback no longer promotes generic `-ing` nominal phrases
      as actions, and parser fallback now prefers finite/root clause heads over arbitrary participles.
    - DONE (numeric lane + second pass): wiki AAO now emits dedicated `numeric_objects`
      at step/event level (separate from `entity_objects` and `modifier_objects`) and runs a
      deterministic sentence second pass for numeric mentions (e.g., percentages) so numbers
      are captured without polluting entity/object lanes.
    - DONE (fact timeline numeric carry-through): HCA timeline fact synthesis now preserves
      step `numeric_objects` alongside `objects`/`modifier_objects` for chronology views.
    - DONE (AAO-all numeric key coalescing): `itir-svelte` wiki timeline AAO-all now
      canonicalizes numeric links/counts by `value|unit` keys in view logic (labels remain
      human-readable), preventing raw-string fan-out (`21` vs `21,500`, `%` variants, compact suffixes).
    - DONE (currency-aware numeric keys): wiki AAO numeric normalization now preserves currency
      symbols/prefixes (`$`, `US$`, `A$`, `€`, `£`) and emits deterministic currency-bearing
      keys (e.g., `$5.6trillion` -> `5.6e12|usd`, `$500,000` -> `500000|usd`), with
      matching AAO/AAO-all view-side key parsing/labels.
    - DONE (numeric key contract alignment): removed legacy scale-currency unit tags
      from canonical keys (`trillion_usd` etc.); scale+currency now normalizes to
      scientific value + currency unit, and event numeric-object dedupe prefers
      currency-bearing mentions over scale-only duplicates.
    - DONE (date-fragment numeric suppression hardening): numeric extraction now
      suppresses day/year fragments when they occur inside date-like entity spans
      (including month+digit EVENT phrases such as `September 11`) and slash-date
      forms (`9/11`), so date anchors stay temporal and do not leak into
      `numeric_objects` / `numeric_claims`.
    - DONE (requester targets from request-verbs): AAO requester lane now also
      tags request targets from request-signal verbs with infinitival complements
      (e.g., `urged Congress to ...` -> requester=`Congress`) using dependency
      structure first, with the legacy `at X's request` pattern retained.
    - DONE (definite-article actor hygiene): actor/subject surface cleanup now
      strips a single leading `the` token (`the United States` -> `United States`)
      to reduce identity fragmentation in actor lanes.
    - DONE (source-pack per-row citations): AAO extractor now preserves timeline-row
      `url`/`path` metadata as `citations[]` follow hints (`provider=source_document`)
      so source packs can surface doc provenance directly in graph views.
    - DONE (step numeric re-injection guard): step-level numeric-claim merge now
      respects sentence-level allowed numeric keys, preventing filtered date
      fragments from being reintroduced into step lanes.
    - DONE (AAO numeric lane ordering): `wiki-timeline-aoo` numeric lane/context
      now sort by numeric magnitude (key value + unit), not lexical label order.
    - DONE (context anchor precision rendering): `wiki-timeline-aoo-all` context rows now display
      event anchor precision directly (day/month/year from the event anchor) rather than downcasting
      to the currently selected time bucket granularity.
  - Numeric ontology alignment (follow-up)
    - DONE: Align `Magnitude.id` formatting (`src/models/numeric_claims.py:magnitude_id`) with
      `docs/numeric_representation_contract_20260213.md` so scientific values remain scientific
      in IDs (e.g. `5.6e12|usd` must not render as `5600000000000|usd`).
    - TODO (cross-time mention lane): add non-synthetic `MENTIONS_EVENT` overlay edges for
      referenced global events (event mention != timeline row insertion), with explicit frame scope.
    - TODO (numeric ontology v0.1): implement materialized numeric entities and claim structures
      from `docs/numeric_representation_contract_20260213.md`:
      - `Magnitude` registry (value+unit identity),
      - `QuantifiedClaim` (sig figs, interval, modality, scope),
      - `RangeClaim` / `RatioClaim` structured lanes,
      - `NumericSurface` phenotype provenance per claim.
    - TODO (wrong-type orthogonal taxonomy): implement machine-stable wrong-type
      dimensions from `docs/ontology.md` / `docs/roadmaps/DB_ROADMAP.md`:

## Decision Outcome Distributions (Descriptive-Only)
- Spec: `SensibLaw/docs/judicial_decision_behavior_contract.md`
- DONE: Implemented deterministic descriptive aggregations over `CaseObservation`
  (counts + Beta-Binomial + Gamma-Poisson) with:
  - explicit SliceDeclaration required (no silent defaults),
  - mandatory corpus disclosure (`n_total`, observed `time_min/time_max`),
  - mandatory statistical interpretation guard,
  - individual-level grouping disabled by default (opt-in required).
- DONE (ridge-logistic + tail contract): expose contracted aggregation APIs for:
  - ridge-logistic MAP association fits (coefficients only; no prediction surfaces),
  - deterministic lognormal tail fitting (parameters + derived tail summaries),
  both enforcing the same slice+disclosure contract as counts/Beta/Gamma.
- DONE: Minimal `CaseObservation` v0.1 exists as a stable input record type in
  `src/judicial_behavior/model.py` (explicit IDs only; no identity inference).
- TODO: Optional storage schema: materialize `case_doc` + typed `case_feature`
  with evidence spans and rebuildable derived stats caches (if/when persistence
  is required beyond curated in-memory datasets).
      - `InterferenceModeType`,
      - `DutyStructureType`,
      - `DefenceType`,
      - explicit mapping from `wrong_type_catalog_seed.yaml` entries to these
        dimensions (without replacing existing `WrongType` IDs).
    - TODO (liability stack crosswalk consistency): keep the compressed
      System/Norm/Doctrine/Event crosswalk synchronized with canonical L0-L6
      ontology docs and DB roadmap naming to avoid layer-number drift.
    - TODO (requirements register v2 follow-through): implement the newly documented
      `R11..R23` backlog from `docs/wiki_timeline_requirements_v2_20260213.md`,
      with priority on:
      - identity/non-coercion invariants and formatting-identity separation (`R7..R9`),
      - quantified conflict tri-state and conflict engine (`R15`) after the
        claim-bearing baseline (`R16`) now emitted in extractor output,
      - numeric semantic role typing expansion (`R11`),
      - granularity-safe temporal comparison and anchor graduation (`R14`, `R19`, `R20`),
      - typed edge-basis metadata + frame-scope validation hard-fail checks (`R22`),
      - optional CMP/CMPL view projection as a non-mutating display transform.
      - keep the "Architecture Gap Closure Matrix (10-point review)" section in
        `docs/wiki_timeline_requirements_698e95ec_20260213.md` current as a provenance map,
        while updating implementation status in `docs/wiki_timeline_requirements_v2_20260213.md`.
    - DONE (numeric role typing baseline): wiki AAO now emits step-scoped `numeric_claims`
      with parser-first governing-verb alignment and deterministic role labels
      (transaction_price/personal_investment/revenue/cost/rate/count/percentage_of).
    - DONE (numeric claim context enrichment): step/event `numeric_claims` now include
      structured normalization (`normalized.value/unit/scale/currency/magnitude_id`)
      plus explicit time attribution fields (`time_anchor` and inline `time_years`).
    - DONE (numeric expression/surface split baseline): step `numeric_claims`
      now carry parser-derived `expression` (mantissa/scale/exponent/sig-fig/coercion)
      and `surface` (symbol/spacing/separator/hash) metadata, separated from
      canonical magnitude identity key.
    - TODO (numeric role typing expansion): broaden taxonomy + conflict/claim integration
      beyond baseline role mapping and extend coverage for additional finance/event patterns.
    - TODO (sourcing/attribution ontology v0.1): implement sourcing/attribution
      requirements (`R17..R18`) from
      `docs/wiki_timeline_requirements_v2_20260213.md` using
      `docs/sourcing_attribution_ontology_20260213.md`:
      - `SourceEntity`, `Attribution`, `ExtractionRecord` model objects,
      - deterministic id helpers and chain-cycle guard,
      - graph/store integration for attribution attachments on claim-bearing AAO lanes (without role pollution),
      - attribution-aware metadata in quantified conflict outputs.
    - DONE (requester lane fidelity baseline): requester extraction now
      canonicalizes possessive/title forms (e.g. `President Obama's` -> `Barack Obama`)
      and adds deterministic fallback from request-step subjects when possessor
      extraction is absent.
    - DONE (subject/article normalization baseline): actor and step-subject
      labels now strip leading definite article (`the X` -> `X`) deterministically
      to prevent subject-lane fragmentation (`the United States` vs `United States`).
    - DONE (requester coverage validator baseline): extractor now emits
      top-level `requester_coverage` counters
      (`request_signal_events`, `requester_events`, `missing_requester_event_ids`)
      to flag request-action events that still resolve to no requester actor.
    - DONE (actor coalescing contract): consolidate wiki timeline AAO actor/subject
      coalescing rules into a single deterministic spec:
      `SensibLaw/docs/actor_coalescing_contract.md`.
    - DONE (requester coverage UI diagnostics baseline): AAO-all now wires
      `requester_coverage` into `req:none` projection checks:
      - selecting `req:none` shows extractor-level counters (`request_signal_events`,
        `requester_events`, `missing_requester_event_ids`) and current-window counts,
      - `req:none` now maps to `missing_requester_event_ids` so gap rows are inspectable
        in context instead of always returning zero rows,
      - requester lane includes a `req:none` diagnostics node when window gaps exist.
    - DONE (source + lens lanes baseline): AAO-all now renders non-role
      `Source` and `Lens` lanes, wired to action nodes with `context` edges:
      - source lane labels include source-entity/provider/parser provenance,
      - lens lane labels include extraction-profile and event lens tags
        (claim-bearing and SL-lane markers),
      - context panel now shows per-row `sources` and `lenses` chips.
    - TODO (requester coverage UI test assertions): add automated assertions for
      `req:none` diagnostics/warning states in UI checks.
    - TODO (source/lens lane test assertions): add automated assertions for
      Source/Lens lane node presence and context-edge rendering states.
    - DONE (claim-bearing + attribution baseline): wiki AAO now emits
      profile-driven `claim_bearing` tags on steps/events and event-level
      `attributions` (direct/reported), plus top-level `source_entity` and
      `extraction_record` metadata for provenance.
    - DONE (epistemic de-hardcode baseline): claim-bearing classification now
      runs through `src/nlp/epistemic_classifier.py` with dependency-first
      scoring (`ccomp`/`xcomp` + modal/deontic/eventive cues) and profile lexical
      fallback, replacing extractor-hardcoded epistemic verb defaults.
    - DONE (R24 baseline implementation): parser-agnostic action morphology mapping
      now lives in `src/nlp/ontology_mapping.py` and extractor `action_meta`
      fields are emitted as canonical enums (`tense/aspect/verb_form/voice/mood/modality`)
      with deterministic `unknown` fallbacks; mapping behavior is test-covered.
  - Freeze schema versions after any final tweaks; bump versions explicitly if changed.
  - Decide next sprint direction (A compliance simulation, B cross-doc norm topology, C human interfaces).
  - Official decision behavior (descriptive-only) — TODO:
    - DONE: Implemented `src/official_behavior` descriptive aggregation module
      aligned to `docs/official_decision_behavior_contract.md`:
      - deterministic, order-independent aggregations,
      - explicit SliceDeclaration required (no silent defaults),
      - corpus disclosure (`n_total`, time bounds),
      - individual-level grouping disabled by default (`allow_individuals=true` required for `official_id`).
    - DONE: Added projection-only `DecisionObservation` view + mapping helpers
      per `docs/decision_observation_projection_contract.md`.
    - DONE: Added a versioned feature schema doc for a concrete political slice:
      `docs/official_behavior_feature_schema_us_exec_foreign_policy_iraq_v1.md`.
  - TiRCorder integration (Layer 0–1 alignment):
    - Normalize TiRCorder transcripts/notes into `Document` → `Sentence` → `Token` with `TextBlock` provenance.
    - Populate `lexemes`, `concepts`, `phrase_occurrences` from TiRCorder text streams.
    - Map `Utterance` ↔ `Sentence` via `UtteranceSentence` for speaker/time alignment.
    - Resolve TiRCorder `speakers` into `Actor` + detail/alias tables (keep `Actor` minimal).
    - Add finance tables (`accounts`, `transactions`, `transfers`) and link via `FinanceProvenance` + `EventFinanceLink`.
    - Adopt deterministic NLP + ingestion utilities (normalizers, matchers, rate-limited fetchers).
  - Sprint 9 UI hardening (read-only, non-semantic) — ✅ done:
    - Fixture-mode rendering for Text & Concepts, Knowledge Graph, Case Comparison, Obligations tabs.
    - Test fixtures under `tests/fixtures/ui` + forbidden language checks.
    - Playwright smoke (opt-in) asserting fixture render + no mutation controls/forbidden terms.
    - Utilities tab: “Labs / not covered by Sprint 9 invariants” banner; read-only.
  - Sources (ingestion) discipline:
    - Add AustLII SINO search adapter (deterministic URL builder + parser; rate-limited).
    - Add AustLII fetch adapter (HTML/PDF, provenance only, rate-limited).
    - Add citation normalisation helpers + tests (JADE/AustLII/PDF alignment).
    - Add storage guard tests (DB delta, compression ratio) using one PDF fixture.
    - [x] Add IR/token compression invariants doc and keep it authoritative (`docs/ir_invariants.md`).
    - [x] Add token duplication guard + overlap growth pytest using Mabo + overlapping citation fixture.
    - [x] Add citation-follow stability test (token hash before/after) and concept identity test across ingest/Text & Concepts.
    - [x] Extend research-health CLI to include `tokens_per_document_mean` with golden fixture test.
    - [ ] Keep the research-health compression ratio guard aligned with the Shannon-limit regression and triage any departures.
    - [x] Add marginal vocabulary density (MVD) to corpus stats output for diagnostics.
    - [ ] Extend corpus_stats to report token entropy proxy + empirical compression ratio, with per-doc and corpus-level tests.
    - [ ] Define deterministic span-promotion rules to approximate LZ phrase discovery (thresholds, stability tests, reversible expansion).
    - [ ] Specify a stable "phrase atom" contract (naming/IDs, auditability, cross-run determinism).
    - [ ] Implement one-pass span promotion and leftmost-longest rewrite with deterministic tie-breakers.
    - [x] Define Layer 3 span-only role hypothesis contract (SpanRoleHypothesis) and storage location.
    - [x] Specify promotion gates from Layer 3 spans to ontology tables (auditable, deterministic).
    - [x] Implement promotion gate evaluation + receipts (rule IDs, evidence spans).
    - [x] Implement SpanSignalHypothesis extractors (glyphs, OCR, layout signals).
    - [x] Document Layer 3 families explicitly (Role, Structure, Alignment, Signal).
    - [x] Add Layer 3 regeneration tests (drop spans, rebuild, compare metadata + ordering).
    - [ ] Add SL/ITIR overlay boundary contract (targets, layers, evidence pointers) and keep it mutation-free.
    - [ ] Sync SL/ITIR overlay boundary contract with SB forbidden-field list and red-team boundary rules.
    - [ ] Define SB activity_event ingest contract (read-only, immutable boundaries, annotation-only overlays).
    - [x] Add corpus characterisation doc tying MVD/rr5 regimes to SL vs ITIR.
    - [x] Add static guard test preventing `tokenize_simple` creep beyond metrics modules.
    - [x] Document tokenizer/sentence/structure contract and AIF-core note (`docs/tokenizer_contract.md`).
    - Add page_map capture (page → token range) and page-stability test (different pagination, identical tokens).
    - Add ingest modes (`legal` default, `general`) with enrichers gated and `--force-legal` override.
    - Implement large-doc path: boilerplate pre-strip + 4k/20% chunking + repetition metadata (`repeat_ratio`, `max_chunk_jaccard`, `chunk_count`).
    - Extend research-health to report `chunked_documents` and `repeat_ratio_mean`.
    - Map ITIR/TIRC primitives to SL profile (lossless vs lossy) and codify interpretive → SL mention handshake.
    - Document generic vs legal logic parsers and outputs (`docs/logic_parsers.md`).
    - Document Principle Relationship Map pipeline and invariants (`docs/principle_relationship_map.md`).
    - Document structural vs interpretive logic graph layers and naming (`docs/logic_graph_layers.md`).
  - Citation-follow expansion (bounded, non-semantic):
    - Implement citation extraction → resolution → fetch → ingest with depth/volume bounds.
    - Default resolver order: already-ingested → local → JADE (MNC) → AustLII (URL/search) → unresolved.
    - Add orchestration tests and ensure provenance is recorded outside identity hashes.

- Backlog (deferred)
  - Ingestion-to-query foundation — PDF → parsed artifacts → SQLite/FTS → traversal API → Graphviz DOT render with NLP Sprints 1–2 hooks (reactivate explicitly if needed).

- Dependencies/infra to track
  - None new for S6; continue using spaCy/Graphviz/SQLite baseline.







Move below raw to docs:
› $update-docs-todo-implement Good — this is exactly the kind of thing that needs to be formalised, not improvised.

  You want a **“When to Walk” policy for Wiki resolution** inside the SL / ITIR extractor.

  Meaning:

  > When should the system automatically resolve to a Wikipedia / Wikidata entity,
  > and when should it stop and require user intervention?

  Below is a formal, deterministic policy you can drop into `docs/contracts/wiki_resolution_policy.md`.

  ---

  # Wiki Resolution Policy (“When to Walk”)

  ## Purpose

  Prevent:

  * Over-eager external linking
  * Silent mis-resolution
  * Actor coalescing corruption
  * Cross-domain hallucinated merges

  Ensure:

  * Deterministic, auditable resolution
  * Explicit user consent for ambiguous cases
  * No semantic drift

  ---

  # Core Principle

  > Wiki resolution is optional enrichment, not a source of truth.

  The canonical identity inside SL is internal.
  External IDs are evidence layers.

  ---

  # Definitions

  ### WALK

  A “walk” means:

  * Querying Wikipedia/Wikidata
  * Attempting external entity resolution
  * Assigning external identifiers
  * Merging based on external identity

  ### AUTO-WALK

  System performs resolution without user interaction.

  ### HARD-WALK

  System requires user disambiguation before resolution.

  ### NO-WALK

  System does not attempt external resolution.

  ---

  # Resolution States

  Each `ActorCanonical` has:

  ```json
  {
    "wiki_status": "UNRESOLVED | AUTO_LINKED | USER_CONFIRMED | AMBIGUOUS | BLOCKED"
  }
  ```

  ---

  # When to AUTO-WALK

  AUTO-WALK is allowed only if all conditions are satisfied.

  ## A1 — High Confidence Exact Title Match

  * Exact surface == Wikipedia page title
  * AND entity type matches (PERSON vs ORG vs EVENT)
  * AND no competing disambiguation pages

  Example:

  * “George W. Bush” → exact page exists → AUTO-WALK allowed

  ---

  ## A2 — Unique Wikidata Candidate

  If:

  * Only one candidate entity returned
  * Name + type match
  * No competing entities with similar name

  Then AUTO-WALK.

  ---

  ## A3 — Explicit User Intent

  If the user says:

  > “Link actors to Wikipedia”
  > “Resolve to Wikidata”
  > “Enrich with wiki IDs”

  AUTO-WALK allowed (still deterministic).

  ---

  # When to HARD-WALK (Require Disambiguation)

  The system must STOP and ask for clarification if:

  ## H1 — Disambiguation Page

  Surface maps to:

  * Multiple valid Wikipedia pages
  * Person vs place conflict
  * Same-name different individuals

  Example:

  * “George Bush”
  * “John Howard”
  * “Walker Bush”

  System output:

  ```
  AMBIGUOUS_WIKI_ENTITY
  Candidates:
  1. George H. W. Bush
  2. George W. Bush
  3. George Bush (footballer)
  Please disambiguate.
  ```

  ---

  ## H2 — Surname-Only Mentions

  If mention is:

  * Single surname
  * Title + surname (“President Bush”)

  System must not AUTO-WALK.

  Use internal document context first.
  If still ambiguous → HARD-WALK.

  ---

  ## H3 — Two-Token Ambiguity

  Two-token names without middle initial:

  * “George Bush”
  * “John Smith”

  Require disambiguation unless:

  * Document contains earlier fully-qualified mention
  * Internal canonical already linked confidently

  ---

  ## H4 — Type Conflict

  If NER says:

  * ORG
    But wiki returns:
  * PERSON primary candidate

  STOP.

  ---

  ## H5 — Cross-Jurisdiction Name Collision

  If:

  * Australian context
  * Name common in multiple jurisdictions
  * No contextual anchor

  HARD-WALK.

  ---

  # When to NO-WALK

  ## N1 — No User Intent + Low Confidence

  If:

  * Confidence below threshold
  * Name too generic
  * Only substring match

  Do nothing.

  Internal canonical only.

  ---

  ## N2 — Legal Placeholder Entities

  Do NOT walk:

  * “the Appellant”
  * “the Respondent”
  * “the Court”
  * “the Diocese” (unless explicitly resolved by user)
  * “the Minister”

  These are role entities, not identity entities.

  ---

  ## N3 — Structural Entities

  Do not walk:

  * Section numbers
  * Act names (unless specifically in enrichment mode)
  * Legal doctrines
  * Common-law principles

  External linking here causes ontology contamination.

  ---

  # Deterministic Confidence Model

  Every wiki resolution must produce:

  ```json
  {
    "decision": "AUTO_LINKED | AMBIGUOUS | BLOCKED",
    "confidence_score": 0.0-1.0,
    "signals": {
      "exact_match": true,
      "type_match": true,
      "unique_candidate": true,
      "context_support": 0.75
    }
  }
  ```

  AUTO-WALK threshold must be:

  ```
  confidence >= 0.95
  AND no ambiguity flags
  ```

  Otherwise HARD-WALK.

  ---

  # Help Me Disambiguate Case

  When HARD-WALK is triggered, system emits:

  ```json
  {
    "needs_user_input": true,
    "reason": "MULTIPLE_WIKI_CANDIDATES",
    "candidates": [
      {"title": "...", "description": "..."},
      {"title": "...", "description": "..."}
    ]
  }
  ```

  No resolution occurs until user confirms.

  ---

  # Anti-Corruption Rule

  External resolution must NEVER:

  * Change surface text
  * Alter token spans
  * Replace canonical name
  * Merge internal actors based solely on wiki ID

  External ID is metadata only.

  ---

  # Logging Requirement

  All WALK decisions must be logged:

  ```
  wiki_resolution.log
  ```

  Include:

  * mention_id
  * actor_id
  * decision
  * candidate list
  * rule triggered
  * ruleset_hash

  So when you see “Walker Bush” again, you can trace exactly which rule misfired.

  ---

  # Architectural Insight

  This policy ensures:

  * Internal ontology is primary.
  * External resolution is enrichment, not identity.
  * Ambiguity is preserved, not erased.
  * No silent merges.
  * No regex-based shortcuts.

  ---

  If you'd like, next I can:

  * Convert this into a strict state-machine diagram
  * Write pseudo-code for `resolve_wiki(actor)`
  * Or define a formal threshold scoring function for deterministic confidence

  Which level do you want to go to?
   Ah. Good clarification.

  You mean:

  > When should the wiki extractor walk internal link trees / categories recursively
  > vs stop and treat the current page as a leaf?

  That’s a completely different policy from entity disambiguation — and much more dangerous if not formalised.

  Below is a strict, deterministic “When to Walk” policy for **internal link graph traversal** in the wiki ingestion layer.

  ---

  # Wiki Internal Graph Walk Policy

  *(SL / ITIR deterministic ingestion rules)*

  ---

  # Core Principle

  > Walking internal links is a controlled graph expansion operation, not exploration.

  If you don’t constrain it, you get:

  * explosion in node count
  * topic drift
  * semantic contamination
  * time-based instability
  * nondeterministic ingestion results

  So we define walking as a bounded, rule-driven operation.

  ---

  # Definitions

  ### SEED PAGE

  The page explicitly requested or selected.

  ### LINK WALK

  Following internal wiki hyperlinks from a page.

  ### CATEGORY WALK

  Traversing Wikipedia categories upward or downward.

  ### DEPTH

  Number of hops from seed.

  ### FRONTIER

  Set of candidate pages eligible for next walk.

  ---

  # Walk Modes

  You must explicitly choose one of these modes:

  | Mode               | Description                            | Default?   |
  | ------------------ | -------------------------------------- | ---------- |
  | `NONE`             | No walking                             | Default    |
  | `CONTEXTUAL`       | Walk only links in structured sections | Safe       |
  | `ENTITY_GRAPH`     | Walk only entity-type links            | Controlled |
  | `CATEGORY_BOUNDED` | Walk categories under constraints      | Dangerous  |
  | `FREE`             | Follow everything                      | Forbidden  |

  Default must be `NONE`.

  ---

  # When to Walk

  Walking internal links is allowed only if at least one condition is met.

  ---

  ## W1 — Explicit User Instruction

  User says:

  * “Expand related entities”
  * “Walk internal links”
  * “Build graph from this page”
  * “Expand category tree”

  Then walking is allowed under bounded mode.

  ---

  ## W2 — Structured Context Expansion

  If ingestion mode is:

  ```
  mode = CONTEXTUAL
  ```

  Then you may walk only links appearing in:

  * Infobox fields
  * “See also” section
  * “Main article” references
  * Direct biographical relations (e.g., spouse, successor)

  Not body-text links.

  ---

  ## W3 — Typed Entity Graph Mode

  If:

  ```
  mode = ENTITY_GRAPH
  ```

  Then walking allowed only for links whose type matches allowed set.

  Example:

  If seed is PERSON:

  * Allow links to OFFICE held
  * Allow links to ORGANISATION
  * Allow links to COUNTRY
  * Disallow links to:

    * Pop culture references
    * Awards
    * Random hyperlinks

  You must filter by entity class.

  ---

  # Hard Stop Conditions

  Walking must stop if any condition triggered.

  ---

  ## S1 — Depth Limit

  ```
  max_depth = 1 (default)
  max_depth = 2 (explicit override only)
  ```

  Never exceed depth 2 without explicit user confirmation.

  ---

  ## S2 — Node Explosion Threshold

  If:

  ```
  frontier_size > threshold
  ```

  Example:

  ```
  threshold = 50 nodes
  ```

  Stop and require user confirmation.

  ---

  ## S3 — Category Entropy Explosion

  Category walking is extremely unstable.

  Hard rules:

  * Never walk upward categories recursively.
  * Only walk downward if:

    * Category title matches strict filter
    * Category is seed-aligned

  Example:

  Allowed:

  * Category: “Presidents of the United States”

  Not allowed:

  * Category: “American people”
  * Category: “Living people”
  * Category: “20th-century politicians”

  If category size > 200 pages → STOP.

  ---

  ## S4 — Topic Drift Detection

  You must maintain a semantic anchor score.

  If walking candidate page:

  * Has low lexical overlap with seed page
  * Has no shared entities
  * Has different entity class

  Then STOP.

  ---

  # Deterministic Walk Algorithm

  Pseudocode:

  ```python
  def walk(seed_page, mode, max_depth=1):
      visited = set()
      frontier = {seed_page}
      depth = 0

      while depth < max_depth:
          next_frontier = set()

          for page in frontier:
              if page in visited:
                  continue

              visited.add(page)

              candidates = extract_links(page)

              filtered = filter_by_mode(candidates, mode)

              if len(filtered) > NODE_THRESHOLD:
                  raise WalkRequiresConfirmation()

              next_frontier.update(filtered)

          frontier = next_frontier
          depth += 1

      return visited
  ```

  ---

  # What Must Never Be Walked Automatically

  * All internal links in article body
  * All category parents recursively
  * Templates
  * Navigation boxes
  * Portal links
  * Lists of “Notable X”
  * Chronology pages

  These cause uncontrolled expansion.

  ---

  # Determinism Requirement

  Given:

  * Same seed
  * Same mode
  * Same depth
  * Same filter rules

  The output graph must be identical.

  No random order.
  No heuristic ranking without deterministic seed.
  No probabilistic sampling.

  ---

  # Logging Requirements

  Every walk operation must record:

  ```json
  {
    "seed": "George W. Bush",
    "mode": "ENTITY_GRAPH",
    "max_depth": 1,
    "visited_count": 12,
    "stopped_reason": "DEPTH_LIMIT",
    "ruleset_hash": "..."
  }
  ```

  So graph shape is auditable.

  ---

  # Suggested Default Behaviour for SL

  Default extraction:

  ```
  mode = NONE
  max_depth = 0
  ```

  Meaning:
  Only parse the requested page.
  Do not walk.

  If user says:

  > “Expand actor graph one level”

  Then:

  ```
  mode = ENTITY_GRAPH
  max_depth = 1
  ```

  Nothing more.

  ---

  # Why This Matters for Your Actor Bug

  If you walk loosely:

  George W. Bush → Bush → Walker Bush → random category

  You accidentally:

  * Merge actors
  * Create fake coalescing
  * Corrupt timeline extraction

  Graph explosion leads directly to identity contamination.

  ---

  # Clean Separation of Concerns

  Extraction layer:

  * Parse page
  * Extract mentions
  * Resolve locally

  Graph expansion layer:

  * Walk under strict policy

  Never mix them.

  ---

  If you'd like next, I can:

  * Design a category-safe traversal model
  * Or propose a formal “Graph Expansion Contract” aligned with ITIR ingestion manifests
  * Or define a drift-detection metric so you mathematically bound expansion stability

  Which direction?
   want the next vertical slice: define the explicit CommitmentActionLink payload shape (link provenance + constraint tags) so this module can be fed from an ingest pipeline without inventing linkage logic. && ## 1) Category-safe traversal model

  ### Design goals

  * **Bounded**: hard caps on depth, fanout, and total nodes.
  * **Stable**: minimal dependence on Wikipedia’s shifting category graph.
  * **Auditable**: every edge added has a recorded reason + rule ID.
  * **Scope-preserving**: only categories that reinforce the seed’s intended domain.

  ### Core idea

  Treat category traversal as **two separate operations**:

  1. **Category selection** (which categories are even eligible)
  2. **Member selection** (which pages within eligible categories are eligible)

  Both must pass strict gates.

  ---

  ### A. Category classes (classification is deterministic)

  Classify categories by their title and structural properties:

  **C0: Administrative / maintenance** (always block)

  * Title matches: `Living people`, `Births`, `Deaths`, `Articles`, `CS1`, `Pages`, `All Wikipedia`, `Use dmy`, `Short description`, etc.
  * Also: hidden categories / tracking categories if detectable.

  **C1: Broad demographic / time buckets** (default block)

  * `20th-century`, `21st-century`, `American people`, `Politicians`, `Writers`, `Male`, `Female` etc.
  * These cause explosion and drift.

  **C2: Role / office / institutional** (preferred allow)

  * `Presidents of the United States`, `Justices of the High Court of Australia`, `Prime Ministers of…`
  * These are typically “tight” and domain-relevant.

  **C3: Event / topic** (allow with anchor match)

  * `September 11 attacks`, `Iraq War`, `Global financial crisis`
  * These drift easily—require stronger anchor checks.

  **C4: Navigational list categories** (block unless explicitly requested)

  * `…related lists`, `…lists`, `…in popular culture`, etc.

  You implement this with a deterministic title-pattern ruleset (not regex in semantic layers—put it in the traversal policy module and treat it as *graph hygiene*, not entity meaning).

  ---

  ### B. Traversal policy (safe defaults)

  **Default parameters**

  * `max_depth_down = 1` (seed → category → members)
  * `max_depth_up = 0` (never walk parents automatically)
  * `max_categories_per_page = 12`
  * `max_members_per_category = 80` (hard stop)
  * `max_total_nodes_added = 300` per expansion request
  * `max_total_edges_added = 800`

  **Category eligibility gates**
  A category is eligible only if:

  1. **Not blocked by class** (`C0/C1/C4` blocked)
  2. **Has acceptable size**

     * `|members| <= max_members_per_category`
  3. **Anchor match passes** (see drift metric below)

     * `anchor_score(category) >= τ_cat`
  4. **Category “tightness” passes**

     * `tightness(category) >= τ_tight`

  **Member eligibility gates**
  A member page is eligible only if:

  * Page type is acceptable (main/article namespace; not a list page unless requested)
  * `anchor_score(page) >= τ_page`
  * It has at least one of:

    * shared canonical entity with seed (e.g., same office, same party, same institution) **OR**
    * shared infobox type (if you capture it) **OR**
    * link-back / reciprocal link (optional, deterministic check)

  **Traversal direction**

  * Only “downward”: seed → categories → members
  * No “category graph wandering” (no category → category edges) unless user explicitly asks for hierarchical category maps.

  ---

  ### C. “Safe category set” per domain

  Make it **domain-dependent**:

  For *people* pages:

  * allow `C2` strongly, `C3` cautiously
    For *laws / cases*:
  * categories are often messy; prefer link-based traversal (citations) not categories.

  So category traversal should be **off by default** for legal corpora; on for Wikipedia biographies only when the user wants a “graph”.

  ---

  ### D. Stop conditions (must halt and require user)

  Stop if any triggers:

  * `category_count > max_categories_per_page`
  * `members_count > max_members_per_category`
  * `total_nodes_added > max_total_nodes_added`
  * `drift_risk > τ_risk` (defined later)
  * `too_many_low_anchor_hits` (e.g., >30% of candidate members below τ_page)

  When stopping, emit a deterministic “needs user decision” payload listing:

  * the categories you would have walked
  * their sizes
  * top 10 candidate members by anchor_score
  * reason codes

  ---

  ## 2) Formal Graph Expansion Contract aligned with ITIR manifests

  This is a contract between:

  * **Extractor** (wiki_timeline_aoo_extract)
  * **Expansion engine** (internal walk system)
  * **Manifest / provenance** (ITIR ingest)

  ### A. Contract object model

  **GraphExpansionRequest**

  ```json
  {
    "request_id": "gx:req:20260213:000123",
    "seed": {
      "source_type": "wikipedia",
      "page_title": "George W. Bush",
      "page_id": "wp:en:George_W._Bush"
    },
    "mode": "CATEGORY_BOUNDEDIGOR_SAFE_V1",
    "bounds": {
      "max_depth_down": 1,
      "max_categories_per_page": 12,
      "max_members_per_category": 80,
      "max_total_nodes_added": 300,
      "max_total_edges_added": 800
    },
    "allow": {
      "category_classes": ["C2", "C3"],
      "namespaces": ["article"],
      "page_types": ["biography", "office", "event"]
    },
    "deny": {
      "category_classes": ["C0", "C1", "C4"],
      "title_prefixes": ["Lists of", "Outline of"],
      "title_contains": ["in popular culture"]
    },
    "anchor": {
      "seed_signature_id": "sig:…",
      "tau_category": 0.65,
      "tau_page": 0.60,
      "tau_tightness": 0.25
    },
    "determinism": {
      "ruleset_hash": "sha256:…",
      "sort_key": "anchor_score_desc_then_page_id",
      "snapshot": {
        "dump_id": "wikidump:enwiki-2026-02-01",
        "timestamp_utc": "2026-02-13T03:11:00Z"
      }
    }
  }
  ```

  **GraphExpansionResult**

  ```json
  {
    "request_id": "gx:req:20260213:000123",
    "status": "OK|STOPPED_NEEDS_USER|BLOCKED",
    "stop_reason": null,
    "added_nodes": [
      {"node_id":"wp:en:…","type":"PAGE","title":"…","anchor_score":0.71},
      {"node_id":"wp:cat:…","type":"CATEGORY","title":"…","tightness":0.33}
    ],
    "added_edges": [
      {"src":"wp:en:George_W._Bush","dst":"wp:cat:Presidents_of_the_United_States","rel":"IN_CATEGORY","reason":"CAT_C2_ALLOWED"},
      {"src":"wp:cat:Presidents_of_the_United_States","dst":"wp:en:Barack_Obama","rel":"HAS_MEMBER","reason":"MEMBER_ANCHOR_PASS"}
    ],
    "audit": {
      "counts": {"categories_seen": 9, "members_seen": 431, "members_kept": 63},
      "drift": {"risk": 0.18, "mean_anchor": 0.72, "low_anchor_frac": 0.07},
      "blocked_categories": [
        {"title":"Living people","reason":"C0_BLOCK"}
      ]
    }
  }
  ```

  ### B. ITIR ingestion manifest integration

  Add an **expansion section** to your existing ingest manifests (same pattern you use for fetch/parse):

  **itir_manifest.json (addition)**

  ```json
  {
    "artifact_id": "itir:artifact:wiki:timeline:2026-02-13",
    "inputs": [
      {"type":"wiki_snapshot","dump_id":"enwiki-2026-02-01","path":"…"}
    ],
    "stages": [
      {"stage":"extract_seed", "tool":"wiki_timeline_aoo_extract.py", "version":"…", "ruleset_hash":"…"},
      {"stage":"graph_expand", "tool":"wiki_graph_expand.py", "version":"…", "ruleset_hash":"…",
       "requests":[ "gx:req:20260213:000123", "gx:req:20260213:000124" ],
       "results_path":"artifacts/graph_expansion/results.ndjson"
      }
    ],
    "outputs": [
      {"type":"graph_edges","format":"ndjson","path":"…"},
      {"type":"graph_nodes","format":"ndjson","path":"…"},
      {"type":"audit_log","format":"ndjson","path":"…"}
    ]
  }
  ```

  ### C. Contract invariants (tests)

  * **Determinism**: same snapshot + same request ⇒ identical node/edge sets (byte-stable ordering).
  * **Boundedness**: never exceed any bound; if candidate set would exceed, STOP with reason.
  * **No semantic mutation**: expansion does not change ActorMention surfaces/offsets.
  * **Audit completeness**: every added edge has a `reason` code and can be traced to a request.

  ---

  ## 3) Drift-detection metric to bound expansion stability

  You want a mathematically grounded “topic drift” guardrail that works *without* LLMs and remains deterministic.

  ### A. Seed signature

  Compute a seed “anchor signature” from deterministic features:

  * `E_seed`: set of canonical entities extracted from seed page (people, orgs, offices, countries)
  * `K_seed`: top-N keywords from seed (tf-idf over a fixed snapshot corpus, or simpler: frequency with stoplist)
  * `T_seed`: entity type tag (PERSON/ORG/EVENT) and optionally infobox type if you store it

  Represent seed signature as:

  * sparse weighted vector `v_seed` over keywords + entity IDs.

  ### B. Candidate anchor score

  For a candidate page `p`, compute:

  1. **Entity overlap**
     [
     J_E(p) = \frac{|E_p \cap E_{seed}|}{|E_p \cup E_{seed}|}
     ]

  2. **Keyword cosine similarity**
     [
     C_K(p) = \cos(v_{K,p}, v_{K,seed})
     ]

  3. **Type compatibility**
     [
     S_T(p) =
     \begin{cases}
     1 & \text{if type}(p)=\text{type}(seed) \text{ or allowed pair}\
     0 & \text{otherwise}
     \end{cases}
     ]

  Then define:
  [
  \text{anchor}(p) = w_E J_E(p) + w_K C_K(p) + w_T S_T(p)
  ]
  with fixed weights, e.g. `w_E=0.5, w_K=0.4, w_T=0.1`.

  This is fully deterministic.

  ### C. Category tightness

  A category is “tight” if its members cohere to the seed signature.

  Sample deterministically the first `m` members after sorting by stable key (page_id). Compute:

  * mean pairwise keyword similarity (or mean anchor to seed)
    [
    \mu_{cat} = \frac{1}{m}\sum_{i=1}^{m}\text{anchor}(p_i)
    ]

  * dispersion (variance)
    [
    \sigma^2_{cat} = \frac{1}{m}\sum(\text{anchor}(p_i)-\mu_{cat})^2
    ]

  Define tightness:
  [
  \text{tightness}(cat) = \mu_{cat} \cdot (1 - \min(1,\sigma_{cat}))
  ]
  (or any monotone decreasing function of variance)

  Gate:

  * require `tightness(cat) >= τ_tightness`

  ### D. Drift risk for the whole expansion step

  Let `P_added` be pages accepted in this expansion.

  Define:

  * low-anchor fraction:
    [
    f_{low}=\frac{|{p\in P_{added}: \text{anchor}(p)<\tau_{page}}|}{|P_{added}|}
    ]
  * mean anchor:
    [
    \mu=\frac{1}{|P_{added}|}\sum_{p}\text{anchor}(p)
    ]
  * novelty ratio (how many new entities introduced vs shared):
    [
    r_{novel}=\frac{|E_{added}\setminus E_{seed}|}{|E_{seed}|+1}
    ]

  Then drift risk:
  [
  \text{risk}=a\cdot f_{low}+b\cdot (1-\mu)+c\cdot \min(1,r_{novel})
  ]
  with fixed coefficients e.g. `a=0.5, b=0.3, c=0.2`.

  Hard stop if:

  * `risk > τ_risk` (e.g. 0.35), OR
  * `f_low > 0.20`, OR
  * `r_novel > 1.5` at depth 1

  ### E. Stability guarantee

  This gives you a formal, measurable bound:

  * Expansion cannot proceed if it materially increases novelty or lowers coherence.
  * Categories with huge, heterogeneous membership fail tightness.
  * Drift is *quantified* and logged in the audit.

  ---

  ## Practical defaults I’d ship

  * Category traversal **off** unless user requests expansion.
  * When on:

    * `max_depth_down=1`
    * allow only `C2` by default
    * `τ_page=0.60`, `τ_cat=0.65`, `τ_tightness=0.25`, `τ_risk=0.35`
    * stop on any size threshold breach, emit a disambiguation-style “needs user decision” artifact.

  If you want, I can also write the exact **reason codes** (like `C0_BLOCK`, `SIZE_BLOCK`, `DRIFT_STOP`) and a tiny NDJSON audit schema so Playwright/UI can render “why expansion stopped” in a clean inspector panel.
   ref: https://chatgpt.com/g/g-p-6983ff87bc608191905a33b93daa74f7-sensiblaw/c/698f2732-30f4-83a1-b96e-6ccb306113b1
