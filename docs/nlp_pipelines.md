# NLP Pipeline Processing Rules

This document summarises the processing logic baked into the project’s spaCy-based pipeline and records the current state of the Legal-BERT workflow.

## spaCy pipeline

The spaCy pipeline underpins tokenisation, entity recognition, and rule harvesting. Its processing rules are implemented across the pipeline modules and matcher configuration files.

### Token stream construction

* `SpacyAdapter` loads `en_core_web_sm` (or a blank English pipeline) with the named entity recogniser disabled, providing deterministic tokenisation even when pre-trained weights are unavailable. Each emitted token preserves surface text, lemmas, coarse POS tags, dependency labels, and entity types, while whitespace-only tokens are dropped.【F:src/pipeline/tokens.py†L1-L78】
* The shared adapter is exposed via `get_spacy_adapter()` so downstream code reuses a single cached instance with NER disabled, ensuring consistent segmentation across calls.【F:src/pipeline/tokens.py†L80-L103】

### Sentence segmentation and lemmatisation

* The higher-level adapter in `src/nlp/spacy_adapter.py` attempts to load `en_core_web_sm` with NER disabled, falling back to `spacy.blank("en")` as needed. It guarantees sentence boundaries by adding a `sentencizer` when the pipeline lacks parsing components, and initialises a lookup lemmatiser where possible so every token exposes a lemma even when statistical resources are missing.【F:src/nlp/spacy_adapter.py†L18-L61】【F:src/nlp/spacy_adapter.py†L63-L92】
* `parse()` enforces string inputs, ensures the chosen pipeline can emit sentences, and serialises each sentence span into `{text,start,end,tokens}` records where every token carries text, lemma, POS, dependency label, and character offsets. The helper collapses the pipeline output into `{text, sents}` for downstream consumers.【F:src/nlp/spacy_adapter.py†L94-L140】

### Legal named-entity enrichment

* `_ensure_entity_ruler()` guarantees an `EntityRuler` component is inserted (before `ner` when present), configures it to preserve existing entities, and hydrates it from `patterns/legal_patterns.jsonl`. Each pattern provides labelled templates for references to Acts, cases, and provisions.【F:src/pipeline/ner.py†L33-L82】【F:patterns/legal_patterns.jsonl†L1-L4】
* The custom `reference_resolver` component merges rule-based spans (recorded under `doc.spans['REFERENCE']`) and statistical entities with labels in `REFERENCE`, `PERSON`, `ORG`, or `LAW`. It de-duplicates overlapping spans and normalises the `reference_source` extension so downstream consumers can trace whether a hit came from the pattern set, an entity ID, or the entity label itself.【F:src/pipeline/ner.py†L15-L128】
* `configure_ner_pipeline()` appends the resolver when missing, while `get_ner_pipeline()` caches the configured `Language` object so repeated calls reuse the same spaCy model and legal patterns.【F:src/pipeline/ner.py†L130-L150】

### Dependency harvesting

* `_load_pipeline()` tries to load the small/medium/large English pipelines that ship with spaCy, raising a runtime error with installation guidance if none provide a dependency parser. This ensures dependency-based rules only run when parser weights are installed.【F:src/rules/dependencies.py†L24-L78】
* `_collect_candidates()` iterates each sentence, normalises supported dependency arcs (e.g. coercing `dobj` to `obj` and `root` verbs to `verb`), extracts span text for argument roles, and deduplicates `DependencyCandidate` entries per label. Only arcs from `_SUPPORTED_DEPS` survive, keeping the downstream rule matcher focused on subject/object/complement style relations.【F:src/rules/dependencies.py†L80-L173】
* `get_dependencies()` orchestrates parsing, sentence iteration, and candidate aggregation, returning a `SentenceDependencies` list that buckets dependency roles by sentence text.【F:src/rules/dependencies.py†L195-L229】

### Rule matcher configuration

* `src/nlp/rules.py` registers a shared `Matcher` keyed by spaCy `Vocab` objects. The pattern table covers modalities (`must`, `shall`, `may`, plus negative variants), conditional connectors (`if`, `unless`, `provided that`, etc.), references (sections, parts, Acts), and penalty phrases. Matches are greedily resolved so the longest applicable span wins.【F:src/nlp/rules.py†L1-L89】【F:src/nlp/rules.py†L99-L125】
* Normalisation helpers collapse matched spans into canonical enums. `Modality.normalise()` and `ConditionalConnector.normalise()` convert free-text spans into controlled identifiers, removing duplicates, stripping trailing punctuation, and trimming clause markers so downstream logic trees receive clean modality, condition, reference, and penalty buckets.【F:src/nlp/rules.py†L127-L199】
* `match_rules()` executes the matcher, deduplicates values per semantic role, and returns a `RuleMatchSummary` containing ordered modality choices, canonical conditions, normalised references, and penalties. The first modality becomes `primary_modality`, giving downstream components a deterministic default.【F:src/nlp/rules.py†L201-L266】

### Normalisation rules feeding the pipeline

* Prior to spaCy processing, `normalise()` rewrites domain terminology via the glossary, lowercases the result, and constructs lightweight `Token` objects with guessed POS, lemma, and morphological features. Each token carries a configurable `token._.class_` extension to support later logic-tree labelling. These deterministic guesses provide a fallback when spaCy resources are unavailable, ensuring every pipeline stage receives well-formed token objects.【F:src/pipeline/__init__.py†L1-L208】

## Legal-BERT pipeline

A dedicated Legal-BERT pipeline is not currently implemented in the repository. There are no Legal-BERT model wrappers, transformers dependencies, or configuration files to document—`pyproject.toml` and `requirements.txt` list spaCy and other classical NLP dependencies but omit any Hugging Face or BERT packages. As soon as a Legal-BERT workflow is added, its preprocessing and postprocessing rules should be captured alongside the spaCy summary above.【F:pyproject.toml†L10-L36】【F:requirements.txt†L1-L19】
