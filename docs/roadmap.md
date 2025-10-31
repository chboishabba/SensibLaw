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
