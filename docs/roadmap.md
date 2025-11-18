# SensibLaw roadmap

This roadmap captures the focus areas we are driving in parallel with the
near-term deliverables outlined in the README. The objective is to ship a
deterministic, provenance-aware pipeline that plugs directly into Gremlin while
providing a streamlined viewer for legal reasoning outputs.

## 1. Provenance-first extraction stack (DX-101, DX-102)

- Publish `extract-stack/docker-compose.yml` that orchestrates Apache Tika,
  OCRUSREX, and a provenance sidecar under a non-root, no-egress posture.
- Implement `provenance/sidecar.py` + `provenance/schema.json` to coordinate
  text extraction, compute input/output hashes, and emit receipt JSON with tool
  versions, page maps, and container digests.
- Expose a `bin/extract_text` CLI wrapping the sidecar so upstream systems can
  request text with or without OCR and receive deterministic provenance bundles.
- Back the stack with integration tests (`tests/extract/test_extract_text.py`)
  that cover native and image-only PDFs and assert identical receipts across
  reruns.

## 2. Gremlin-aligned pipeline orchestration (ORCH-201 to ORCH-203)

- Document the Gremlin node contract in `docs/gremlin_node_contract.md`,
  clarifying inputs, outputs, `previous_results`, and provenance expectations for
  each stage.
- Provide `pipelines/sensiblaw_logic_graph.json` that Gremlin can import without
  code edits, defining the DAG from extraction through graph ingestion and
  result export.
- Build containerised nodes under `nodes/` with Make targets for
  `build-nodes`, `run-pipeline`, and `conformance`, ensuring the same artefacts
  run locally and inside Gremlin.
- Ship `adapters/gremlin_runner.py` capable of executing the pipeline against
  local Docker nodes, streaming receipts, and resuming from persisted
  `previous_results` payloads.

## 3. Standardised node execution & logic tree formalisation (NODE-301, NODE-302)

- Introduce `sdk/node_base.py` that handles stdin/stdout JSON processing,
  structured logging, exit codes, and metrics for every node.
- Define shared schemas (`schemas/inputs.schema.json`,
  `schemas/outputs.schema.json`, `schemas/error.schema.json`) so nodes validate
  their contracts automatically.
- Update reference nodes (`normalise`, `token_classify`, `logic_tree`,
  `graph_ingest`) to consume the SDK, emit provenance metadata, and honour the
  shared schemas.
- Add `tests/nodes/test_contracts.py` with fixtures that confirm schema
  compliance, deterministic outputs, and consistent error handling across all
  nodes.
- Capture today’s word-catching behaviour (entry points, concept triggers,
  junk filters) as a design note and translate it into a deterministic logic tree
  representation that the `logic_tree` node can execute. This includes
  documenting control flow transitions, boundary conditions, and override hooks
  so clause decisions remain explainable and auditable.

## 4. Reasoning viewer and embedding (UI-401, UI-402)

- Deliver `ui/streamlit_app.py` as a read-only viewer that loads pipeline result
  bundles, renders proof trees, highlights source text spans, and inspects
  knowledge graph neighbourhoods.
- Document embed mode via `ui/embed.md` and `ui/config.toml`, ensuring the
  Streamlit app runs headless and is iframe-safe for Gremlin panels.
- Describe the result bundle contract in `docs/result_bundle.md`, detailing
  `result.json`, per-node receipts, and highlight payloads to guarantee
  round-trippable job archives.
- Provide `gremlin/iframe.html` as a minimal wrapper that Gremlin can host to
  launch the Streamlit viewer with `?job_id=` routing.

## Cross-cutting principles

- Every node and service emits version metadata (`tool_name`, `semver`,
  `git_sha`, `image_digest`) so receipts can be traced and audited.
- Receipts for each pipeline step are stored under `run/receipts/` with
  timestamped filenames to support resumability and compliance reviews.
- Containers run as non-root with outbound network disabled by default (except
  where OCR models require downloads), aligning with the security posture agreed
  with Gremlin.
- Success metrics: <90s time-to-result on a 10-page PDF, deterministic reruns
  for identical inputs, and a one-click "Open Reasoning Viewer" experience for
  Gremlin operators.

# SensibLaw Roadmap — spaCy Integration Milestone

The spaCy integration milestone transitions SensibLaw from regex-first parsing to a
full NLP stack that produces structured tokens, sentences, and dependency graphs ready
for logic-tree assembly. This document captures the deliverables, phased rollout, and
definition of done for the milestone.

## NLP Integration — Current vs Target Deliverables

| Category | **Current State ("As-is")** | **Target State ("To-be")** | **Key Deliverables** |
| --- | --- | --- | --- |
| **Tokenization** | Hand-rolled regex (`\w+`) and manual text splitting. No sentence boundaries, no offsets beyond character indexes. | Deterministic tokenization with sentence boundaries, offsets, and lemmatization from `spaCy` (or Stanza via adapter). | • `src/nlp/spacy_adapter.py` implementing `parse()` → returns `{sents: [{text, start, end, tokens: [{text, lemma, pos, dep, start, end}]}]}`<br>• Unit tests verifying token alignment vs original text (`tests/nlp/test_spacy_adapter.py`). |
| **POS & Lemmas** | None. `normalise()` only lowercases and applies glossary rewrites. | Each token enriched with `POS`, `morph`, and `lemma_` for downstream classification (actor/action/object inference). | • Extend adapter output to include `lemma_`, `pos_`, `morph`.<br>• Add `Token.set_extension("class_", default=None)` for logic tree tagging. |
| **Dependency Parsing** | None. Rule extractors rely on regex (`must`, `if`, `section \d+`). | Dependency tree available per sentence (`nsubj`, `obj`, `aux`, `mark`, `obl`, etc.) for clause role mapping. | • Use `spaCy` built-in parser or `spacy-stanza` (UD).<br>• Expose `get_dependencies()` helper returning role candidates.<br>• Test fixture: “A person must not sell spray paint.” → `nsubj=person`, `VERB=sell`, `obj=spray paint`. |
| **Sentence Segmentation** | Not explicit — one clause per doc or regex breaks on periods. | Automatic sentence boundary detection from spaCy pipeline. | • Enable `sents` iterator from `Doc`.<br>• Add `Sentence` object to data model (`src/models/sentence.py`). |
| **Named Entity Recognition (NER)** | None. Only concept IDs from Aho–Corasick triggers. | Reuse spaCy’s built-in NER (`PERSON`, `ORG`, `LAW`) + optional `EntityRuler` for legal-specific entities. | • `patterns/legal_patterns.jsonl` for Acts, Cases, Provisions.<br>• Integrate `entity_ruler` pipe; expose hits as `REFERENCE` spans. |
| **Rule-based Matchers** | Regex in `rules.py` finds modalities, conditions, and refs manually. | Replace manual regex with `Matcher` and `DependencyMatcher` patterns. | • `src/nlp/rules.py` defining matchers for `MODALITY`, `CONDITION`, `REFERENCE`, `PENALTY`.<br>• Unit tests verifying expected matches per pattern. |
| **Custom Attributes / Logic Tree Hooks** | N/A — logic tree built from scratch after regex tokens. | Every token/span carries `._.class_` = {ACTOR, ACTION, MODALITY,…}, ready for tree builder. | • `Token.set_extension("class_", default=None)`.<br>• Populate via matcher callbacks.<br>• Verify full coverage (no unlabeled non-junk tokens). |
| **Integration into pipeline** | `pipeline.normalise → match_concepts` only. No NLP pipe. | New `pipeline/tokens.py` module invoked between `normalise` and `logic_tree`. | • Update `pipeline/__init__.py`:<br>`tokens = spacy_adapter.parse(normalised_text)`.<br>• Pass token stream to `logic_tree.build(tokens)`. |
| **Fallback / Multilingual** | English-only regex. | Wrapper can swap Stanza/UD when language ≠ "en". | • Optional `SpacyNLP(lang="auto")` detects LID and selects model.<br>• Add `fastText` or Tika LID hook. |
| **Testing & Validation** | No automated linguistic tests. | Deterministic tokenization, POS, dep, and matcher coverage tests. | • `tests/nlp/test_tokens.py` (token counts, sentence segmentation).<br>• `tests/nlp/test_rules.py` (pattern hits).<br>• Golden expected JSON per input sample. |

## Milestone Phases

| Phase | Goal | Outputs |
| --- | --- | --- |
| **1. Infrastructure** | Add spaCy dependency & adapter | `spacy_adapter.py`, tests, Makefile target `make test-nlp`. |
| **2. Enrichment** | POS, lemmas, deps, NER | Updated `parse()` output, `Sentence` + `Token` models. |
| **3. Rule layer** | Replace regexes with Matcher/DependencyMatcher | `rules.py` with predefined legal patterns. |
| **4. Integration** | Insert into main pipeline | Call from `pipeline/__init__.py` between normalise → logic_tree. |
| **5. Validation** | Ensure 100 % token coverage + deterministic tests | `pytest` suite; golden span JSON for sample cases. |

## Definition of Done

1. **spaCy adapter works standalone** (`python -m src.nlp.spacy_adapter "A person must..."`) → emits JSON tokens.
2. **POS/dep/lemma coverage ≥ 99 %** (non-junk tokens labeled).
3. **Rule matchers** identify `MODALITY`, `CONDITION`, `REFERENCE`, `PENALTY` on sample corpus.
4. **Logic tree builder** accepts token stream directly (no regex token split).
5. **Regression tests** confirm deterministic spans and labels.
6. **Docs updated** (`docs/nlp_integration.md`) describing pipeline order and config.

## One-line Summary

**From:** regex & glossary only → **To:** spaCy-powered tokenization + syntactic tagging + rule matchers feeding the logic-tree assembler.

---

## spaCy pipeline hardening and ontology integration (updates from 18/11/2025)

The spaCy pipeline now underpins tokenisation, sentence segmentation, NER, and rule matching for SensibLaw. The modules and files in scope are summarised in `docs/nlp_pipelines.md`, including adapters (`src/nlp/spacy_adapter.py`, `src/pipeline/tokens.py`), NER configuration (`src/pipeline/ner.py`, `patterns/legal_patterns.jsonl`), dependency harvesting (`src/rules/dependencies.py`), and rule matchers (`src/nlp/rules.py`). This section tracks the hardening work needed to stabilise those components and wire their outputs into the ontology layer.

### Hardening scope

- **Tokenisation & sentence segmentation:** Confirm deterministic segmentation across the adapters noted in `docs/nlp_pipelines.md`, align offsets with the downstream `RuleAtom` builder, and add guardrails for blank pipelines so fallback lemmatisation does not drift from the reference models.
- **NER and rule matching:** Finalise the `EntityRuler` pattern set and reference resolver so legal references, actors, and penalties flow through the same `REFERENCE` spans that the matcher consumes; ensure matcher normalisation maintains canonical modality/condition/reference/penalty buckets.
- **RuleAtom → ontology tables:** Persist rule-atom outputs (party/role, modality, condition, reference, penalty, dependency candidates) into the ontology tables introduced in `DATABASE.md` (LegalSystem, WrongType, ProtectedInterest, ValueFrame, Event/Harm). Add DAO/ingestion hooks so every `RuleMatchSummary` slot maps to the relevant table rows and linkage tables.

### Milestones

1. **Pipeline verification** — Lock deterministic token and sentence boundaries across the spaCy adapters, including tests for the modules listed in `docs/nlp_pipelines.md`.
2. **Ontology binding** — Map rule-atom fields into ontology tables with repeatable ingestion jobs and round-trip validation (RuleAtom → DB → graph export).
3. **Legal-BERT workflow introduction** — Bring the planned Legal-BERT semantic layer online to enrich actor classes, interest detection, and wrong-type inference ahead of graph persistence, reusing the spaCy spans and dependency candidates already defined in `docs/nlp_pipelines.md`.
