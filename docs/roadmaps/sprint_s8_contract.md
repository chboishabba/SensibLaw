# Sprint 8 Contract — Human Review & Audit (Non-Semantic)

Scope: enable humans to inspect, annotate, and export obligation state without adding reasoning or compliance logic.

## Allowed
- Read-only display of obligations, activation results, alignments, and cross-doc topology.
- Human-authored annotations (`ReviewerNote`, `DisagreementMarker`) stored separately from core payloads.
- Deterministic exports (JSON/PDF bundles) for audit.

## Forbidden
- Compliance judgments, risk scoring, or precedence resolution.
- Ontology expansion, synonym/normalisation of text.
- Mutation of obligation identities, activation state, or topology.
- Hidden defaults, auto-approvals, or “fix-ups.”

## Required invariants
- Annotations never alter core payloads; removal of annotations yields identical hashes.
- UI actions are idempotent and read-only by default.
- Every human action is attributable (author + timestamp) and exportable.

## Delivery boundary
- Any new behavior that affects semantics requires a new sprint and schema version.
- Streamlit surfaces are consumers only; no business logic is added there.
