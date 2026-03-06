# Regex Policy: Semantic Layers

Status: Draft (2026-03-04)

## Rule (Non-Negotiable)
Regex is allowed for **raw text ingestion and formatting**, but **forbidden**
for semantic interpretation.

Allowed:
- ingestion
- text cleaning
- formatting

Forbidden:
- entity extraction
- actor resolution
- legal meaning inference
- ontology classification

## Rationale (Short)
Regex operates on surface strings. Semantic layers operate on structured
objects (actors, actions, conditions). Regex in semantic layers breaks
determinism, reproducibility, and correctness, and it silently encodes
fragile rules.

## Layer Map
1. **Layer 0 — Ingestion**
   - OK: regex for cleanup, citation stripping, whitespace normalization.
2. **Layer 1 — Tokenization / Parsing**
   - OK: deterministic tokenizers, grammars, parser outputs.
3. **Layer 2 — Semantic Extraction**
   - NOT OK: regex or string heuristics.

## Current Regex Usage (Targets for Transition)
The following locations are regex-heavy and must be treated as **transition
targets** where regex should be reduced or eliminated from semantic logic:

- `SensibLaw/scripts/wiki_timeline_aoo_extract.py`
- `SensibLaw/scripts/wiki_timeline_extract.py`
- `SensibLaw/scripts/hca_case_demo_ingest.py` (only allow regex in ingestion/cleaning)
- `SensibLaw/scripts/wiki_candidates_distribution_report.py` (acceptable as analysis-only)
- `SensibLaw/scripts/dbpedia_lookup_api.py` (cleaning-only allowed)

UI/formatting helpers (allowed if limited to presentation):
- `SensibLaw/sensiblaw_streamlit/document_preview.py`
- `SensibLaw/sensiblaw_streamlit/tabs/knowledge_graph.py`

## Tests (Required)
These tests gate upgrades and ensure regressions do not reintroduce regex into
semantic layers.

1. **Static lint: semantic regex ban**
   - Fail if `re.` usage appears in semantic extraction modules.
   - Initial target set:
     - `SensibLaw/scripts/wiki_timeline_aoo_extract.py`
     - `SensibLaw/scripts/wiki_timeline_extract.py`
     - `SensibLaw/src/nlp/`
     - `SensibLaw/src/` semantic model layers (actors/claims/ontology)

2. **Allowlist-based regex audit**
   - Permit regex only in:
     - ingestion/cleaning helpers
     - formatting/UI helpers
   - Require explicit allowlist entries with comments explaining why.

3. **Determinism guard**
   - For any remaining regex in ingestion, ensure outputs are byte-identical for
     the same input and engine version.

4. **Semantic extraction parity**
   - When regex is removed from a semantic module, add a fixture that asserts
     parser-based outputs are deterministic and span-anchored.

## Transition Plan (Docs-First)
1. Document each regex in semantic modules and label it as:
   - `ingestion_cleaning`
   - `formatting`
   - `semantic` (must be removed)
2. Replace `semantic` regex usage with parser-first logic or ontology lookup.
3. Add tests above before removing legacy regex logic.

## References
- `docs/planning/compression_engine.md`
- `SensibLaw/docs/tokenizer_contract.md`
