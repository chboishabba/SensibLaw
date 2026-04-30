# Legal-follow graph layers: authority boundary and operator steering

## Layer order (current code reality)
- `Phi` substrate: canonical normalized atoms are the base ownership layer.
- Composed candidate layer: source-anchored candidate legal-claim rows (`relation_candidates`) plus promoted latent-graph rows reused as candidate-shape inputs.
- Structural admissibility layer: fail-closed endpoint and edge admissibility over legal-claim assertions (`promote | audit | abstain`).
- Promoted record ownership layer: authoritative ownership remains promoted records, not the derived follow graph.
- Derived/operator layer: `au_legal_follow_graph` is explicitly `derived_only: true, challengeable: true`; operator steering is built in `build_au_legal_follow_operator_view(...)`.

## Structural admissibility boundary
- Node admissibility for legal-claim endpoints is computed from relation promotion status (promoted -> `promote`, otherwise `audit`) and section context.
- Edge admissibility is evaluated per `asserts_*` edge through `evaluate_legal_edge_admissibility(...)`.
- Relation kind and contradiction checks are structural/typed gate checks; they are not lexical-intent inference.
- The legal-follow graph can expose review pressure counts (`assert_edge_admissibility_counts`) but does not become the promotion authority.

## Promoted ownership vs derived views
- Promoted records are extracted from report state and mapped into latent promoted graph rows before reuse.
- Reused promoted rows are still represented inside the derived legal-follow graph as candidate-lineage context (`semantic_basis: promoted_anchor`), not as a new ownership domain.
- Derived follow targets (for example UK/British follow suggestions) are conjecture nodes for review routing only.
- Parliamentary/debate edges are advisory and explicitly non-binding.

## Operator steering boundary
- Operator queue items are derived from:
  - legal-claim nodes + their `asserts_*` admissibility rows
  - derived follow-target suggestions
  - advisory debate records
- Priority/ranking is derived queue policy for review workflow pressure.
- Queue steering never mutates promoted ownership and never upgrades a candidate without the existing promotion path.

## Invariants (must stay explicit)
- `Phi` and promoted records are ownership surfaces.
- Composed candidates and legal-follow graph nodes are challengeable, derived surfaces.
- Admissibility is fail-closed and typed (`promote | audit | abstain`), with reasons carried in edge metadata.
- Operator views are derived steering products over graph state, not a new semantic owner.

## UML freshness note
- Reviewed against:
  - `src/policy/legal_follow_graph.py`
  - `src/fact_intake/review_bundle.py`
  - `src/fact_intake/au_review_bundle.py`
- No `.puml` update is required for this lane because the referenced roadmap diagrams are metasystem/affidavit snapshots and do not currently encode the AU legal-follow admissibility-owner boundary at this level.
