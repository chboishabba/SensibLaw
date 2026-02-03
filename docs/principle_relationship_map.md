# Principle Relationship Map (PRM)

## Purpose
The Principle Relationship Map is the structural, auditable graph of relationships between legal principles, their citing/derived authorities, and applied contexts. It is a read-only projection built from the canonical token/span layer and the logic tree; it does **not** invent semantics.

## Inputs
- **Canonical text & tokens**: authoritative token stream per document version.
- **Logic tree**: spans for clauses, conditions, modalities, exceptions, references.
- **Citations**: normalized keys (MNCs, neutral cites) with provenance.
- **Principle definitions**: curated or extracted principle statements keyed by normalized concept IDs.
- **Mentions**: span-anchored occurrences of principles in documents.

## Pipeline (conceptual)
1) **Ingest & normalize**  
   PDF → text → deterministic tokens → logic tree (no reasoning). Page map is side metadata.

2) **Principle detection**  
   - Match candidate principle phrases in spans (curated lexicons + pattern rules).  
   - Normalize to principle keys (e.g., `principle:abuse_of_process`).
   - Record **mentions**: `(doc_id, token_start, token_end, principle_key, confidence, provenance)`.

3) **Principle anchoring**  
   - Link mentions to enclosing logic tree nodes (CLAUSE/CONDITION/EXCEPTION).  
   - Preserve spans; no text duplication.

4) **Relationship extraction**  
   - From logic tree + citations: derive edges such as `cites`, `applies`, `distinguishes`, `overrules` (directional, provenance-required).  
   - Edges carry provenance (doc_id, span, citation key, optional heuristic tag).

5) **Graph assembly (PRM)**  
   Nodes:
   - Principle nodes (normalized keys, curated metadata)
   - Document nodes (authority/evidence)
   - Mention nodes (span-anchored)
   - Citation nodes (normalized case keys)
   Edges:
   - `mentions` (doc → principle via mention)
   - `supports` / `limits` / `applies` / `distinguishes` / `overrules` (doc ↔ doc, principle ↔ principle), all provenance-backed
   - `cites` (doc → doc) using normalized citation keys
   Storage: append-only, span-referential; no string duplication.

6) **Projection / export**  
   - JSON/SQLite/KG view for downstream UIs.  
   - DOT export for structural inspection (sequence edges non-constraining; tokens omitted by default).  
   - Research-health metrics extended to track principle coverage (future).

## Invariants
- Single lexical authority: no principle text is duplicated; spans remain the source of truth.
- Provenance required: no relationship without `(doc_id, span)` and (where applicable) citation key.
- Non-inventive: PRM does not infer new principles; only records detected mentions and cited relations.
- Deterministic: same inputs → same PRM; ordering is stable.

## Modes
- **Legal** (default): citation normalization + provenance enforcement; unresolved citations are surfaced.  
- **General**: permits non-authority documents; principle detection may still run but relationships require provenance to be recorded.

## Outputs
- Principle coverage per corpus (counts of principles, mentions, supporting/limiting edges).
- Span-addressable graph for UI (hover/snippet via `(doc_id, token_start, token_end)`).
- Optional DOT/SVG for structural debugging (principles vs documents vs mentions).

## Gaps / Next steps
- Formal edge schema and allowed predicates list.  
- Page-map integration for “p. N” locators in exports.  
- Large-doc path integration (chunking metadata) without breaking span references.  
- CLI hook to emit PRM slices (e.g., `--graph principle:abuse_of_process --hops 2`).  
