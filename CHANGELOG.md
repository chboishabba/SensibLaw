# Changelog

## Unreleased
- Docs: add canonical v2 requirements register
  (`docs/wiki_timeline_requirements_v2_20260213.md`) and align requirement IDs/status
  for extraction, ontology, attribution, conflict logic, anchor graduation, and validation.
- Docs: mark `docs/wiki_timeline_requirements_v2_20260213.md` as the active
  tracker and keep `docs/wiki_timeline_requirements_698e95ec_20260213.md` as
  provenance/history mapping.
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
  (`$`, `US$`, `A$`, `€`, `£`) in canonical numeric keys, including scale +
  currency composites (e.g., `$5.6trillion` -> `5.6|trillion_usd`).
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
