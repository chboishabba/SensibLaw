# Changelog

## Unreleased
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
