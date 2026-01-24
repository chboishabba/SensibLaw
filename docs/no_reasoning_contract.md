# No-Reasoning Contract (Sprint S6.6)

Purpose: freeze the descriptive-only boundary for SensibLaw. These rules are **hard constraints**. Any future code/tests must fail if they are violated.

## Forbidden behaviors
- No compliance judgements (never answer “is X compliant?”).
- No legal reasoning/defeasibility or conflict resolution.
- No ontology/taxonomy expansion (no synonym/role mapping, no external registries).
- No invented obligations, edges, actors, actions, scopes, or lifecycle triggers.
- No cross-clause inference or cross-document norm resolution unless explicitly introduced in a later sprint with new invariants.
- No semantic normalization beyond whitespace/punctuation collapse; keep text-derived spans only.

## Structural guardrails
- Obligations require explicit modal triggers (`must`, `shall`, `may`, `must not`, etc.).
- Edges (conditions/exceptions) require explicit trigger tokens; scopes/lifecycle are attachments only.
- Identity/diff surfaces (OBL-ID, CR-ID) stay frozen; scopes/lifecycle must **not** affect identity.
- Alignment “modified” entries must correspond to actual metadata deltas (e.g., scopes/lifecycle text changes), not formatting noise.
- Feature flags for actor/action binding must continue to gate identity participation.

## Red-flag checks to keep
- No obligations emitted without modal text.
- No edges emitted without trigger tokens.
- Identity unchanged when scopes/lifecycle are added/removed.
- Alignment reports no “modified” when texts are identical (formatting/numbering noise).
- Normalized actor/action/object tokens must be drawn from the clause text (substring after lowercase/whitespace cleanup).

## Change control
- Schema versions (query/explanation/alignment) are frozen at v1. Changing fields requires a new version bump and tests.
- If any future capability needs interpretation, add a new sprint with explicit invariants; do not widen S6 semantics silently.
