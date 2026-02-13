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
      keys (e.g., `$5.6trillion` -> `5.6|trillion_usd`, `$500,000` -> `500000|usd`), with
      matching AAO/AAO-all view-side key parsing/labels.
    - DONE (context anchor precision rendering): `wiki-timeline-aoo-all` context rows now display
      event anchor precision directly (day/month/year from the event anchor) rather than downcasting
      to the currently selected time bucket granularity.
    - TODO (cross-time mention lane): add non-synthetic `MENTIONS_EVENT` overlay edges for
      referenced global events (event mention != timeline row insertion), with explicit frame scope.
    - TODO (numeric ontology v0.1): implement materialized numeric entities and claim structures
      from `docs/numeric_representation_contract_20260213.md`:
      - `Magnitude` registry (value+unit identity),
      - `QuantifiedClaim` (sig figs, interval, modality, scope),
      - `RangeClaim` / `RatioClaim` structured lanes,
      - `NumericSurface` phenotype provenance per claim.
    - TODO (requirements register v2 follow-through): implement the newly documented
      `R11..R23` backlog from `docs/wiki_timeline_requirements_v2_20260213.md`,
      with priority on:
      - identity/non-coercion invariants and formatting-identity separation (`R7..R9`),
      - claim-bearing event classification + quantified conflict tri-state (`R15..R16`),
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
    - TODO (numeric role typing expansion): broaden taxonomy + conflict/claim integration
      beyond baseline role mapping and extend coverage for additional finance/event patterns.
    - TODO (sourcing/attribution ontology v0.1): implement sourcing/attribution
      requirements (`R17..R18`) from
      `docs/wiki_timeline_requirements_v2_20260213.md` using
      `docs/sourcing_attribution_ontology_20260213.md`:
      - `SourceEntity`, `Attribution`, `ExtractionRecord` model objects,
      - deterministic id helpers and chain-cycle guard,
      - attribution attachments on claim-bearing AAO lanes (without role pollution),
      - attribution-aware metadata in quantified conflict outputs.
  - Freeze schema versions after any final tweaks; bump versions explicitly if changed.
  - Decide next sprint direction (A compliance simulation, B cross-doc norm topology, C human interfaces).
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
