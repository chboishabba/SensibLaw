# No-Reasoning Contract (Sprint S6.6 → S7)

Purpose: freeze the descriptive-only boundary for SensibLaw. These rules are **hard constraints**. Any future code/tests must fail if they are violated.

## Forbidden behaviors
- No compliance judgements (never answer “is X compliant?”).
- No legal reasoning/defeasibility or conflict resolution.
- No ontology/taxonomy expansion (no synonym/role mapping, no external registries).
- No invented obligations, edges, actors, actions, scopes, or lifecycle triggers.
- No cross-clause inference or cross-document norm resolution unless explicitly introduced in a later sprint with new invariants.
- No semantic normalization beyond whitespace/punctuation collapse; keep text-derived spans only.
- No inferred facts or temporal defaults (“now”, “current time”) in activation metadata.

## Structural guardrails
- Obligations require explicit modal triggers (`must`, `shall`, `may`, `must not`, etc.).
- Edges (conditions/exceptions) require explicit trigger tokens; scopes/lifecycle are attachments only.
- Identity/diff surfaces (OBL-ID, CR-ID) stay frozen; scopes/lifecycle must **not** affect identity.
- Alignment “modified” entries must correspond to actual metadata deltas (e.g., scopes/lifecycle text changes), not formatting noise.
- Feature flags for actor/action binding must continue to gate identity participation.
- Activation is descriptive metadata only: trigger text + declared fact → state; no compliance words; termination outranks activation; missing trigger ⇒ inactive.

## Red-flag checks to keep
- No obligations emitted without modal text.
- No edges emitted without trigger tokens.
- Identity unchanged when scopes/lifecycle are added/removed.
- Alignment reports no “modified” when texts are identical (formatting/numbering noise).
- Normalized actor/action/object tokens must be drawn from the clause text (substring after lowercase/whitespace cleanup).
- Activation cannot occur without lifecycle trigger text; missing facts keep obligations inactive; compliance words forbidden; identity hashes intact.

## Change control
- Schema versions (query/explanation/alignment/activation/projection) are frozen at v1. Changing fields requires a new version bump and tests.
- If any future capability needs interpretation, add a new sprint with explicit invariants; do not widen S6 semantics silently.

## Enforcement map (red-flag tests)
- Ordering + schema stability: `tests/api/test_obligations_snapshots.py` (marked `@redflag`)
- No activation without trigger/facts; no compliance terms; identity intact: `tests/activation/test_activation_contract.py` (`@redflag`)
- Activation precedence and missing facts: `tests/activation/test_activation_simulation.py` (core coverage)
- CLI/API guard rails (read-only surfaces): `tests/cli/test_obligations_cli.py`, `tests/api/test_obligations_endpoints.py` (snapshotted)

Run the red-flag subset alone:
```bash
pytest -q -m redflag
```
