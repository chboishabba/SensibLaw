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

## Composed candidate graph (bridge layer)
- Purpose: hold source-anchored candidate nodes that normalize structural spans into a reusable intermediate surface.
- Contract: each composed candidate node must remain traceable to structural spans and keep normalized `kind` / `value` shape as a derived bridge, not as a rewritten source.
- Admissibility: fail-closed; a candidate may only move forward when the gate can justify `promote`, `audit`, or `abstain` from the preserved evidence.
- Relationship to other layers:
  - sits above the structural graph
  - sits below interpretive overlays and promoted outputs
  - does not invent text, mutate spans, or replace the structural substrate
- Good for: canonical candidate-node normalization, cross-surface reuse, and deterministic review of composed shapes before promotion.

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
- Composed-candidate layer: derived and source-anchored, but still non-authoritative until admissibility promotes it.
- Interpretive layer: hypotheses allowed, but every edge must cite structural spans; no silent text duplication.
