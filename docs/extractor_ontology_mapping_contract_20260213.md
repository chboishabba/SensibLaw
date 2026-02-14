# Extractor -> Ontology Mapping Contract (2026-02-13)

## Purpose
Define a parser-agnostic mapping boundary:
- extractor libraries (spaCy/Babel/date normalizers) produce raw parse artifacts,
- SensibLaw ontology stores canonical semantic fields,
- graph/truth layers never depend on extractor class internals.

This contract prevents ontology coupling to library object models.

## Layer Boundary
1. Extractor layer (spaCy/Babel/date parsing) emits raw analysis.
2. Mapping layer converts raw analysis into canonical ontology fields.
3. Ontology layer stores only canonical fields and stable IDs.

Library objects (`Token`, `Morph`, Babel parser objects) must not be persisted in ontology payloads.

## ActionEvent Mapping (v0.1)

Canonical fields:

```yaml
ActionEventMorphology:
  tense: past | present | future | unknown
  aspect: simple | progressive | perfect | perfect_progressive | unknown
  voice: active | passive | middle | unknown
  mood: indicative | conditional | imperative | subjunctive | unknown
  modality: asserted | reported | projected | estimated | alleged | inferred
  verb_form: finite | infinitive | participle | gerund | unknown
```

### spaCy -> canonical mapping rules

- `Tense`:
  - `Past` -> `past`
  - `Pres` -> `present`
  - `Fut` -> `future`
  - else `unknown`
- `Aspect`:
  - `Perf` + `Prog` -> `perfect_progressive`
  - `Perf` -> `perfect`
  - `Prog` -> `progressive`
  - if finite/infinitive/participle/gerund present and no aspect -> `simple`
  - else `unknown`
- `Mood`:
  - `Ind` -> `indicative`
  - `Cnd` -> `conditional`
  - `Imp` -> `imperative`
  - `Sub` -> `subjunctive`
  - else `unknown`
- `Voice`:
  - passive signal if any child dep in `{auxpass, nsubjpass}` or token dep is `auxpass`
  - otherwise `active`
- `VerbForm`:
  - `Fin` -> `finite`
  - `Inf` -> `infinitive`
  - `Part` -> `participle`
  - `Ger` -> `gerund`
  - else `unknown`
- `Modality`:
  - mapping-layer hint (claim/reporting classifier) preferred
  - default `asserted`

## Action Label Mapping (v0.2)

Canonical action labels for AAO extraction must be selected via parser-first
classification:

1. spaCy token stream (`VERB`/`AUX`) provides candidate predicates.
2. Candidate predicate lemmas map to canonical action labels via ontology-aware
   action lemma tables.
3. Dependency context resolves ambiguous lemmas deterministically
   (e.g., `commission` + `into` -> `commissioned_into`; `give` + `birth` ->
   `gave_birth`).
4. Regex pattern matching is fallback-only when parser/classifier signals are
   unavailable or empty, and must emit explicit fallback warnings.

This keeps event/action ontology mapping parser-anchored and minimizes
surface-pattern drift.

## Semantic Backbone Determinism (WordNet/BabelNet)

For ontology mapping in SL/ITIR:

1. WordNet and BabelNet are treated as deterministic lexical/semantic resources
   (knowledge graphs), not generative models.
2. Canonical mapping decisions must not depend on LLM generation in the
   authoritative extraction path.
3. If Word Sense Disambiguation (WSD) is used, the production mapping path must
   be deterministic and version-pinned (rule-first or model-version pinned with
   fixed thresholds/tie-breakers).
4. Synset linkage belongs to the semantic normalization layer; raw library
   objects/results must not be persisted as ontology identity fields.
5. Regex remains fallback-only for extraction misses/hygiene paths and must emit
   explicit fallback warnings when used.

### Deterministic Synset Mapping Contract

When semantic resources are enabled in profile (`semantic_backbone.resource`):

1. Mapping must run through a deterministic synset resolver only (no
   probabilistic/generative disambiguation in authoritative extraction).
2. Resource versions must be pinned in profile and validated at runtime before
   mapping is used.
   - `semantic_version_pins.wordnet`: required when WordNet is enabled.
   - `semantic_version_pins.babelnet_table_sha256`: required when BabelNet-table
     mapping is enabled (pins the lemma->synset table artifact).
   - `semantic_version_pins.synset_action_map_sha256`: required when semantic
     mapping is enabled (pins synset->action mapping).
3. Synset-to-action mappings must be explicit, profile-provided, and stable.
4. Tie-breaks across multiple candidate synsets must be deterministic
   (ordered by canonical synset id).
5. Canonical selection must be single-action or abstain:
   - if mapped candidates yield exactly one unique canonical action, select it
     and choose `min(synset_id)` as the supporting synset id;
   - if mapped candidates yield multiple different canonical actions, return no
     canonical mapping (abstain) and preserve candidates in diagnostic metadata
     where available.
5. If requested resources/version pins are unavailable or mismatched, extraction
   must fail fast rather than silently downgrade into non-authoritative behavior.

### Abstention Precedence

If synset mapping is enabled and yields an explicit ambiguity (multiple competing
canonical actions), the authoritative extraction path must abstain and must not
fall back to weaker surface heuristics (regex patterns) for that sentence.

## Numeric/Temporal Mapping Boundary (status)
- Numeric identity contract lives in `docs/numeric_representation_contract_20260213.md`.
- Temporal granularity contract is tracked in `docs/wiki_timeline_requirements_v2_20260213.md` (`R13`, `R14`).
- Extractor output may include helper metadata, but ontology identity remains key-based and parser-agnostic.
- Numeric claim payloads now emit parser-derived `expression` and `surface`
  metadata separately from canonical `value|unit` identity keys.

## Invariance Requirements
1. Ontology fields must remain stable if extractor model version changes.
2. Missing extractor features map to `unknown` (never null object references).
3. Canonical enums must not leak raw extractor strings (e.g., no `Past` in ontology fields).
4. Mapping behavior must be deterministic and test-covered.

## Current Implementation Scope
- Implemented baseline for ActionEvent morphology mapping in extractor pipeline
  via `src/nlp/ontology_mapping.py` and `scripts/wiki_timeline_aoo_extract.py`.
- Action label extraction now follows spaCy-first classifier flow with
  regex fallback guards (see `src/nlp/event_classifier.py` and
  `scripts/wiki_timeline_aoo_extract.py` integration).
- Extraction profile now carries a normalized `semantic_backbone` block and
  enforces deterministic/non-generative settings (`llm_enabled=false`,
  deterministic `wsd_policy` only); invalid profile settings fail fast.
- Numeric and temporal full ontology mapping remains partially implemented (see TODO/register).
