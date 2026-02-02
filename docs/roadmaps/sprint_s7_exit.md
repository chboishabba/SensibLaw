# Sprint 7 Exit (Frozen)

Status: **Closed.** No further semantic or structural changes allowed without a new versioned sprint.

## What is frozen
- Interfaces (API + CLI) for obligations, explanations, projections, alignment, activation.
- Activation semantics (descriptive only) and payload `obligation.activation.v1`.
- Cross-document topology grammar, schema, and extractor (`obligation.crossdoc.v1`).
- All snapshots under `tests/snapshots/s7/`.

## Forbidden without new sprint
- Any reasoning, compliance judgment, or inferred facts.
- Ontology/synonym expansion for obligations or topology.
- Identity hash changes for obligations or references.
- Schema edits to `*.v1` files (use a new version instead).
- Implicit activation, temporal inference, or precedence logic.

## Red-flag checklist (must stay green)
- `pytest -q -m redflag`
  - Forbidden phrases emit no edges.
  - Activation never fires without explicit trigger + fact.
  - No compliance language in payloads.
  - Cross-doc edges only with explicit references and allowed phrases.
  - Obligation identities unchanged by topology.

## Change control
- Any semantic change requires:
  1) New schema version (`*.v2`),
  2) Updated docs describing intent,
  3) New snapshots and red-flag coverage.
