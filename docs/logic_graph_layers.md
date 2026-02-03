# Logic graph layers: structural vs interpretive

## Structural graph (what exists now)
- Purpose: show how text is deterministically decomposed into spans/scopes.
- Built from: tokenizer + sentence/clause segmentation + logic tree node typing.
- Node types: ROOT, CLAUSE, CONDITION, MODAL, EXCEPTION, REFERENCE, TOKEN.
- Edge types:
  - STRUCTURAL (parent/child containment) — drives hierarchy.
  - SEQUENCE (traversal/ordering) — non-constraining, may be hidden.
- Guarantees: span-anchored, deterministic, non-inferential. No claims or reasoning added.
- Good for: ingestion/debugging, reproducibility, verifying offsets and scopes.

## Interpretive graph (future / ITIR overlay)
- Purpose: capture reasoning/claims/hypotheses over the structural substrate.
- Nodes: claims, actors, hypotheses, timelines, principle mentions (span-backed).
- Edges: supports / contradicts / applies / distinguishes / overrules (provenance-required), uncertainty flags.
- Built after ingestion; may be branched/forked; always points back to SL spans.
- Must never mutate structural spans or invent text.

## Naming and visualization
- Call the current export a **Span Decomposition Graph** (structural).
- Interpretive graphs should be a separate export/profile (ITIR overlays).
- Structural DOT default: hides TOKEN nodes, makes SEQUENCE edges `constraint=false` (already implemented).
- Interpretive DOT/KG: distinct node/edge palette; always includes span provenance.

## Invariants to keep distinct
- Structural layer: no inference, deterministic, span-only references.
- Interpretive layer: hypotheses allowed, but every edge must cite structural spans; no silent text duplication.
