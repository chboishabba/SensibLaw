# COMPACTIFIED_CONTEXT

## Purpose
Compact snapshot of intent while applying the get-shit-done and update-docs-todo-implement workflows for S7–S9 execution.

## Objective
Close S7–S9 (TextSpan authority, cross-doc topology v2, read-only UI) with docs/TODO sequencing and deterministic tests.

## Near-term intent
- Preserve span authority and read-only surfaces; do not add reasoning or compliance logic.
- Keep Layer 3 regeneration deterministic and promotion gates auditable.

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
- Wikidata ontology lane now uses the newest pinned slice/revision as the active
  baseline for routine diagnostics; explicit historical rewind checks are now
  tracked as a separate review-triggered process because they are useful but add
  non-trivial context overhead.
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

## Sources
Chat-sourced statements are now referenced from the compression/ITIR overlay
discussion (see `698218f7-9ca4-83a1-969d-0ffc3d6264e4:1-80`).
Use `CONVERSATION_ID:line#` citing the line-numbered excerpts in
`__CONTEXT/last_sync/`.
