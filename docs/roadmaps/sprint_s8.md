# Sprint S8 — Cross-Document Norm Topology (Non-Judgmental)

Thesis: expose how norms relate across documents without asserting equivalence,
precedence, or correctness.

## Goals
- Show relationships between obligations across statutes, versions, and cases.
- Keep everything descriptive, never evaluative.
- Build graph views, not graph logic.

## Non-goals
- No "applies over" or conflict resolution.
- No priority rules or inferred identity.
- No reasoning over meaning.

## Deliverables

### S8.1 Norm reference graph
- Nodes: obligation atoms.
- Edges (typed, read-only): references, modifies, repeals, cites.
- Edges must be text-derived.

### S8.2 Cross-doc alignment views
- Show similar wording, shared actors, shared objects.
- Alignment is hypothesis, not identity.

### S8.3 Graph projection APIs
- Deterministic graph JSON.
- Adjacency-only traversal, stable ordering.

### S8.4 Safety rails
- Explicit "NOT legal advice / NOT reasoning" banner.
- Tests rejecting forbidden terms: conflict, overrides, controls, prevails.

## Exit criteria
- Render a topology graph without asserting meaning.
- No edge implies hierarchy or correctness.
- All edges trace to spans.

## Delivery rules
- Deterministic ordering for payloads.
- No semantic normalization or identity changes.
