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
- Numeric and temporal full ontology mapping remains partially implemented (see TODO/register).
