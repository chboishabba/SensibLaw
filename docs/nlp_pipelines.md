# NLP Pipeline Processing Rules

This document describes how SensibLaw converts legal text into structured rule atoms and how upcoming semantic inference layers will attach ontology concepts. It separates currently implemented stages from pending semantic layers.

---

## 1. End-to-end NLP pipeline (status overview)

The target pipeline flows through the following stages:

1. Sentence segmentation ✅ (implemented)
2. Clause decomposition ✅ (implemented)
3. Syntactic argument extraction ✅ (implemented)
4. ActorRole → ActorClass mapping 🚧 (planned)
5. Predicate interpretation → Modality extraction ✅ (implemented)
6. Interest-bearing entity identification 🚧 (planned)
7. ProtectedInterest inference 🚧 (planned)
8. ValueFrame inference 🚧 (planned)
9. WrongType candidate inference 🚧 (planned)
10. RuleAtom generation ✅ (implemented)
11. Binding → LegalSource 🚧 (planned)
12. Storage → DB ontology layer ✅ (implemented for RuleAtoms)

Implemented layers are detailed in §2–§5. Planned semantic layers and their expected contracts are defined in §6–§10 with action items for delivery.

---

## 2. spaCy pipeline (implemented)

The spaCy pipeline underpins tokenisation, entity recognition, and rule harvesting. Its processing rules are implemented across the pipeline modules and matcher configuration files.

### 2.1 Token stream construction

* `SpacyAdapter` loads `en_core_web_sm` (or a blank English pipeline) with the named entity recogniser disabled, providing deterministic tokenisation even when pre-trained weights are unavailable. Each emitted token preserves surface text, lemmas, coarse POS tags, dependency labels, and entity types, while whitespace-only tokens are dropped.【F:src/pipeline/tokens.py†L1-L78】
* The shared adapter is exposed via `get_spacy_adapter()` so downstream code reuses a single cached instance with NER disabled, ensuring consistent segmentation across calls.【F:src/pipeline/tokens.py†L80-L103】

### 2.2 Sentence segmentation and lemmatisation

* The higher-level adapter in `src/nlp/spacy_adapter.py` attempts to load `en_core_web_sm` with NER disabled, falling back to `spacy.blank("en")` as needed. It guarantees sentence boundaries by adding a `sentencizer` when the pipeline lacks parsing components, and initialises a lookup lemmatiser where possible so every token exposes a lemma even when statistical resources are missing.【F:src/nlp/spacy_adapter.py†L18-L61】【F:src/nlp/spacy_adapter.py†L63-L92】
* `parse()` enforces string inputs, ensures the chosen pipeline can emit sentences, and serialises each sentence span into `{text,start,end,tokens}` records where every token carries text, lemma, POS, dependency label, and character offsets. The helper collapses the pipeline output into `{text, sents}` for downstream consumers.【F:src/nlp/spacy_adapter.py†L94-L140】

### 2.3 Legal named-entity enrichment

* `_ensure_entity_ruler()` guarantees an `EntityRuler` component is inserted (before `ner` when present), configures it to preserve existing entities, and hydrates it from `patterns/legal_patterns.jsonl`. Each pattern provides labelled templates for references to Acts, cases, and provisions.【F:src/pipeline/ner.py†L33-L82】【F:patterns/legal_patterns.jsonl†L1-L4】
* The custom `reference_resolver` component merges rule-based spans (recorded under `doc.spans['REFERENCE']`) and statistical entities with labels in `REFERENCE`, `PERSON`, `ORG`, or `LAW`. It de-duplicates overlapping spans and normalises the `reference_source` extension so downstream consumers can trace whether a hit came from the pattern set, an entity ID, or the entity label itself.【F:src/pipeline/ner.py†L15-L128】
* `configure_ner_pipeline()` appends the resolver when missing, while `get_ner_pipeline()` caches the configured `Language` object so repeated calls reuse the same spaCy model and legal patterns.【F:src/pipeline/ner.py†L130-L150】

### 2.4 Dependency harvesting (syntactic argument extraction)

* `_load_pipeline()` tries to load the small/medium/large English pipelines that ship with spaCy, raising a runtime error with installation guidance if none provide a dependency parser. This ensures dependency-based rules only run when parser weights are installed.【F:src/rules/dependencies.py†L24-L78】
* `_collect_candidates()` iterates each sentence, normalises supported dependency arcs (e.g. coercing `dobj` to `obj` and `root` verbs to `verb`), extracts span text for argument roles, and deduplicates `DependencyCandidate` entries per label. Only arcs from `_SUPPORTED_DEPS` survive, keeping the downstream rule matcher focused on subject/object/complement style relations.【F:src/rules/dependencies.py†L80-L173】
* `get_dependencies()` orchestrates parsing, sentence iteration, and candidate aggregation, returning a `SentenceDependencies` list that buckets dependency roles by sentence text.【F:src/rules/dependencies.py†L195-L229】

These dependency signals are part of the deterministic local extraction layer.
They may be used as a parser-first backup for relation/role harvesting where
surface matching is insufficient, but they do not carry external ontology
identity themselves. If later enrichment uses Wikidata or related sources, that
must happen downstream over curated actors/concepts/refs rather than by
changing the canonical token/lexeme stream.

### 2.5 Rule matcher configuration

* `src/nlp/rules.py` registers a shared `Matcher` keyed by spaCy `Vocab` objects. The pattern table covers modalities (`must`, `shall`, `may`, plus negative variants), conditional connectors (`if`, `unless`, `provided that`, etc.), references (sections, parts, Acts), and penalty phrases. Matches are greedily resolved so the longest applicable span wins.【F:src/nlp/rules.py†L1-L89】【F:src/nlp/rules.py†L99-L125】
* Normalisation helpers collapse matched spans into canonical enums. `Modality.normalise()` and `ConditionalConnector.normalise()` convert free-text spans into controlled identifiers, removing duplicates, stripping trailing punctuation, and trimming clause markers so downstream logic trees receive clean modality, condition, reference, and penalty buckets.【F:src/nlp/rules.py†L127-L199】
* `match_rules()` executes the matcher, deduplicates values per semantic role, and returns a `RuleMatchSummary` containing ordered modality choices, canonical conditions, normalised references, and penalties. The first modality becomes `primary_modality`, giving downstream components a deterministic default.【F:src/nlp/rules.py†L201-L266】

### 2.6 Normalisation rules feeding the pipeline

* Prior to spaCy processing, `normalise()` rewrites domain terminology via the glossary, lowercases the result, and constructs lightweight `Token` objects with guessed POS, lemma, and morphological features. Each token carries a configurable `token._.class_` extension to support later logic-tree labelling. These deterministic guesses provide a fallback when spaCy resources are unavailable, ensuring every pipeline stage receives well-formed token objects.【F:src/pipeline/__init__.py†L1-L208】

---

## 3. Rule extraction and atom assembly (implemented)

The rule-to-atom workflow is implemented in `src/rules/extractor.py`, `src/rules/__init__.py`, and `src/pdf_ingest.py`.

### 3.1 Sentence scanning and pattern matching

1. `_split_sentences()` scans provision text once, buffering characters until it reaches `.`, `;`, or a newline that is not inside parentheses. This preserves citations such as “(1992) 175 CLR 1” so they remain intact for later reference parsing.【F:src/rules/extractor.py†L44-L86】
2. Each sentence is normalised and fed to `_PATTERNS`, a list containing `_NORMATIVE_PATTERN` and `_OFFENCE_PATTERN`. The first captures “actor + modality (must/may/shall) + rest”; the second recognises “actor commits/is guilty of offence if/when/by rest”, preserving the offence label as part of the modality.【F:src/rules/extractor.py†L9-L36】【F:src/rules/extractor.py†L199-L238】
3. If a sentence opens with `if/when/where/unless`, `_normalise_condition_text()` trims the leading clause and stores it as a preliminary condition before pattern matching begins, so prefixed conditions like “If the Minister is satisfied…” are not treated as actors.【F:src/rules/extractor.py†L120-L196】【F:src/rules/extractor.py†L166-L198】
4. When `_OFFENCE_PATTERN` matches, the offence label is appended to the modality (e.g. “commits the offence of theft”) and the trigger word (`if/when/by`) is reinserted before the remainder of the clause, retaining offence semantics for downstream categorisation.【F:src/rules/extractor.py†L238-L252】

### 3.2 Conditional, scope, and element extraction

5. After a match, `_normalise_condition_text()` strips trailing “then” markers and compresses whitespace, ensuring condition fragments are canonicalised before storage.【F:src/rules/extractor.py†L110-L118】【F:src/rules/extractor.py†L256-L277】
6. If the matched `rest` contains a nested `if/when/unless`, the substring before that marker becomes the action, and the remainder becomes an additional condition, which is merged with any prefix captured in step 3. `scope` clauses beginning with “within” or “under” are cut from the action so that spatial/authority limits can be handled separately.【F:src/rules/extractor.py†L254-L279】
7. `_classify_fragments()` decomposes the action, conditions, and scope into offence elements: it detects exception phrases, fault/mental state terms, result clauses, circumstance modifiers, and remaining conduct text. Each fragment is cleaned with `_clean_fragment()` to drop punctuation, deduplicated case-insensitively, and assigned to roles such as `conduct`, `fault`, `circumstance`, `exception`, and `result`. Scope fragments and inline `if/when` clauses are also treated as `circumstance` entries so downstream logic has a unified bucket.【F:src/rules/extractor.py†L118-L161】【F:src/rules/extractor.py†L162-L219】

### 3.3 Party classification

8. `derive_party_metadata()` (from `src/rules/__init__.py`) normalises the actor string by lowercasing and stripping non-alphabetic characters, then consults the curated taxonomy in `data/ontology/actors.yaml`. Each taxonomy entry defines a canonical `role`, human-readable `who_text`, and a list of aliases; `_match_party()` tests whether any alias appears as a standalone token inside the actor text. If the actor is not found, deterministic fallbacks infer a “defence/accused” party for phrases like “any person” or modalities such as “commits/is guilty of”. Otherwise, the party defaults to `unknown`, signalling that a lint should be raised later.【F:src/rules/__init__.py†L13-L138】【F:data/ontology/actors.yaml†L1-L81】

### 3.4 Rule construction

9. Every successful pattern match becomes a `Rule` dataclass instance holding `actor`, `modality`, `action`, `conditions`, `scope`, and the classified `elements`. The derived `party`, `role`, and `who_text` are stored alongside these attributes so later steps know how to describe the actor even when the raw text lacks detail.【F:src/rules/extractor.py†L280-L320】
10. `_rules_to_atoms()` (in `src/pdf_ingest.py`) consumes the `Rule` list. For each rule it:
    * Copies actor/modality/action text and removes inline parenthetical citations via `_strip_inline_citations()`, capturing any recognised case citations as `RuleReference` objects with `work`, `section`, `pinpoint`, and `citation_text` metadata.【F:src/pdf_ingest.py†L1239-L1302】【F:src/pdf_ingest.py†L1303-L1354】
    * Reconstructs a combined `text` string consisting of actor, modality, action, conditions, and scope, then strips citations again to prevent duplicate references in the resulting atom.【F:src/pdf_ingest.py†L1334-L1369】
    * Instantiates a `RuleAtom` with the canonical party metadata (`party`, `role`, `who_text`) returned by step 8, and stores the condition/scope strings so clients can render them without re-running the regex matcher.【F:src/pdf_ingest.py†L1347-L1380】
    * Converts each offence element fragment (conduct, fault, circumstance, exception, result) into a `RuleElement` labelled as `atom_type="element"`, copying any citations that were attached to the fragment and linking the fragment to glossary candidates via `GlossaryLinker`. Circumstance fragments inherit the parent rule’s conditions when appropriate so the linkage carries the full context.【F:src/pdf_ingest.py†L1381-L1408】
    * Records structured references by linking `RuleReference` instances to glossary entries when possible. This produces machine-readable citations in `rule_atom.references` and eventual legacy atom `refs` values.【F:src/pdf_ingest.py†L1409-L1419】
    * Emits `RuleLint` entries when `party == UNKNOWN_PARTY`, flagging atoms that still need manual actor classification. Lints are stored beside the rule and later flattened into the legacy atom view with `atom_type="lint"`.【F:src/pdf_ingest.py†L1411-L1417】

11. `_rules_to_atoms()` returns a list of `RuleAtom` objects that feed directly into each provision. When a provision is serialised or loaded, `Provision.ensure_rule_atoms()` backfills any missing representations: it converts legacy `Atom` rows into structured `RuleAtom`s (preserving `refs`, `glossary_id`, and metadata) and flattens structured rule atoms back into the legacy schema when needed. This compatibility layer guarantees that every stored provision exposes both the rich structured form and the historical “atom” view used by search indices.【F:src/pdf_ingest.py†L1417-L1420】【F:src/models/provision.py†L573-L760】

### 3.5 Legacy atom flattening

12. `RuleAtom.to_atoms()` maps each structured rule to one or more legacy `Atom` records: the subject atom mirrors the rule’s actor/modality/action text; each `RuleElement` becomes a derived atom tagged with its element role; and any `RuleLint` produces a `lint` atom referencing the offending rule. This deterministic flattening is invoked whenever `Provision.sync_legacy_atoms()` runs, ensuring the SQLite compatibility view (`atoms`) always lines up with the structured representation stored across `rule_atoms`, `rule_atom_elements`, `rule_atom_references`, and related tables.【F:src/models/provision.py†L400-L582】

### 3.6 Legal-BERT pipeline note

A dedicated Legal-BERT pipeline is not currently implemented. There are no Legal-BERT model wrappers, transformer dependencies, or configuration files to document—`pyproject.toml` and `requirements.txt` list spaCy and other classical NLP dependencies but omit any Hugging Face or BERT packages.【F:pyproject.toml†L10-L36】【F:requirements.txt†L1-L19】 Additions should be recorded alongside the spaCy summary when available.

---

## 4. Planned semantic layers and ontology alignment

The following sections describe the intended contracts for upcoming semantic layers. Each includes expected inputs/outputs and action items for implementation.

### 4.1 ActorRole → ActorClass mapping

**Purpose:** Map raw rule actor phrases into ontology concepts (`ActorClass`, `RoleMarker`, `RelationshipKind`) so downstream semantics know what sort of actor the rule addresses.

**Inputs:**

- `Rule` / `RuleAtom` fields (`party`, `role`, `who_text`, dependency-based subject spans)
- Named entities (`PERSON`, `ORG`, `LAW`; references to public bodies, courts, agencies)
- Optional external metadata (case parties, legal source metadata)

**Outputs:**

- `actor_class_id` (e.g., `private.person`, `state.agency`, `community.collective`, `religious.officer`, `corporate.entity`)
- Optional `role_marker_ids` and `relationship_kind_ids` for constraints embedded in the rule
- Provenance: `source = "rule_actor_classifier_v1"`

**Action items:**

- Implement classifier that maps `RuleAtom.party`/`who_text` + NER context to `ActorClass` and optional relationship markers (Ticket: NLP-AC-001).
- Surface unresolved actors as structured lints so they are reviewable in the UI/API (Ticket: NLP-AC-002).

### 4.2 Interest-bearing entity identification

**Purpose:** Detect entities in the clause that could carry protected interests (e.g., whenua, taonga, cultural knowledge, ecosystems).

**Inputs:**

- Dependency parse outputs (`subject`, `object`, `pobj`, `nmod` spans)
- Named entities tagged as locations, cultural groups, natural features, or resources
- Glossary-backed keywords for interest-bearing entities

**Outputs:**

- Normalised entity candidates with span offsets and hints for interest type (resource, place, knowledge, person/community)
- Provenance: `source = "interest_entity_detector_v1"`

**Action items:**

- Add pattern and embedding-based detectors for interest-bearing entities in `src/nlp` (Ticket: NLP-INT-001).
- Store candidate entities on `RuleAtom` for later linking to `ProtectedInterest` (Ticket: NLP-INT-002).

### 4.3 ProtectedInterest inference

**Purpose:** Map interest-bearing entities to ontology `ProtectedInterest` records and their `ProtectedInterestType`/`ValueDimension` descriptors.

**Inputs:**

- Interest-bearing entity candidates from §4.2
- Glossary lookups and ontology tables for interest types
- Contextual clues from conditions/scope and modality (e.g., preservation vs. exploitation)

**Outputs:**

- `protected_interest_id` and `protected_interest_type_id` linked to ontology rows
- Optional `value_dimension_ids` to encode cultural/environmental/economic axes
- Provenance: `source = "protected_interest_inferencer_v1"`

**Action items:**

- Build resolver that links entity candidates to ontology interests using glossary similarity + rule context (Ticket: NLP-PI-001).
- Expose unmatched interests as reviewable tasks with suggested ontology rows (Ticket: NLP-PI-002).

### 4.4 ValueFrame inference

**Purpose:** Infer `ValueFrame` records that express how values (e.g., stewardship, autonomy, equity) are balanced or prioritised in the rule.

**Inputs:**

- Rule modality, conditions, and offence elements (conduct/fault/circumstance)
- Protected interest candidates and actor classes
- Cue phrases indicating value trade-offs or priorities

**Outputs:**

- `value_frame_id` plus scored `value_dimension_ids` indicating the value emphasis
- Provenance: `source = "value_frame_inferencer_v1"`

**Action items:**

- Define cue phrase library and scoring rubric for value dimensions (Ticket: NLP-VF-001).
- Implement inference module that attaches `ValueFrame` candidates to `RuleAtom` records (Ticket: NLP-VF-002).

### 4.5 WrongType candidate inference

**Purpose:** Derive ontology `WrongType` candidates (e.g., offence categories, breaches, duties) from the rule’s conduct/fault/circumstance structure.

**Inputs:**

- `RuleElement` fragments (conduct, fault, circumstance, exception, result)
- ActorClass and ProtectedInterest outputs
- Offence labels captured during pattern matching

**Outputs:**

- `wrong_type_id` and optional `wrong_subtype`/`category` markers
- Linkage between `WrongType` and triggering `RuleElement` fragments
- Provenance: `source = "wrong_type_inferencer_v1"`

**Action items:**

- Train/encode pattern library mapping offence phrases and conduct structures to `WrongType` taxonomy (Ticket: NLP-WT-001).
- Persist candidate scores and rationales alongside `RuleAtom` for curator review (Ticket: NLP-WT-002).

### 4.6 LegalSource binding

**Purpose:** Bind references detected in §2.3 to ontology `LegalSource` records (statutes, cases, treaties, tikanga statements, religious texts).

**Inputs:**

- Normalised references and `reference_source` metadata from the entity ruler
- Provision metadata (work/section identifiers)
- External citation registries where available

**Outputs:**

- `legal_source_id` and optional `norm_source_category_id`
- Anchor metadata (work, section, pinpoint) for cross-linking provisions to ontology sources
- Provenance: `source = "legal_source_binder_v1"`

**Action items:**

- Implement resolver that matches references to `LegalSource` rows using citation text + provision metadata (Ticket: NLP-LS-001).
- Add validation step that flags unresolved or ambiguous sources for manual curation (Ticket: NLP-LS-002).

---

## 5. Storage alignment

Structured RuleAtoms are persisted today; future semantic enrichments should ensure storage of ActorClass, ProtectedInterest, ValueFrame, WrongType, and LegalSource bindings alongside provenance and reviewer status to keep the ontology layer auditable.
