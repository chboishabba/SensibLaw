# Sprint: S6 — Normative Reasoning Surfaces (Non-Judgmental)

## Goal
Expose queryable, explainable, and composable views over the frozen S4–S5 normative lattice **without** adding legal reasoning, compliance judgements, ontologies, or ML. Outputs must remain read-only, deterministic, and identity-neutral.

## Scope
- Read-only query helpers across actor/action/object/scope/lifecycle metadata.
- Explanation/trace payloads that map atoms back to clause IDs and text spans.
- Cross-version obligation alignment reports (unchanged/modified/added/removed with metadata deltas).
- Deterministic view projections (actor-centric, action-centric, timeline, clause-grouped).
- Versioned JSON schemas for obligation, explanation, diff, and graph payloads.
- No-reasoning guardrails and red-flag tests to freeze the descriptive-only contract.

## Constraints
- Clause-local, text-derived only; no ontology lookup, inference, or compliance evaluation.
- Identity/diff invariants (CR-ID, OBL-ID) remain frozen; new surfaces must not alter identities.
- Deterministic ordering for all emitted collections; formatting/OCR noise must not change results.
- Feature flags remain available; new surfaces should respect actor/action binding toggles.

## Deliverables
- S6.1 Query API (read-only filters; flag-respecting).
- S6.2 Explanation surfaces (deterministic atom→span mapping).
- S6.3 Cross-version alignment report with metadata deltas.
- S6.4 Normative view projection builders (actor/action/timeline/clause).
- S6.5 Versioned JSON schemas (obligation, explanation, diff, graph) with backward-compat parsing tests.
- S6.6 Hard-stop guard doc + red-flag tests to prevent reasoning/ontology creep.

## Plan (sequencing)
1) S6.1 Query API → validate payload fidelity without touching identity.
2) S6.2 Explanations → make outputs auditable and stable.
3) S6.3 Alignment → human-readable change summaries atop identity diff.
4) S6.4 View projections → deterministic alternate lenses on the same graph.
5) S6.5 External contracts → freeze schemas for downstream consumers.
6) S6.6 Gate review → enforce “descriptive-only” boundary with tests/docs.

## Acceptance Criteria
- Queries and explanations are deterministic under formatting/OCR/numbering changes and respect actor/action flags.
- Alignment reports show metadata deltas without breaking unchanged identities.
- View projections produce reproducible outputs; no invented nodes or edges.
- Schemas are versioned and backward-compatible; round-trip tests pass.
- Red-flag tests fail if compliance reasoning, ontology expansion, or inference is introduced.
- Full regression suite remains green.

## Risks / Mitigations
- Risk: accidental reasoning creep → Mitigation: red-flag tests and explicit guard doc.
- Risk: schema churn → Mitigation: versioned schemas with backward-compat harness.
- Risk: nondeterministic ordering → Mitigation: stable sort keys across all surfaces.
- Risk: flag bypass → Mitigation: unit tests for actor/action flag interactions on query/explanation outputs.
