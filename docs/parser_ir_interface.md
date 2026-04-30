# Parser, IR, and Signals Interface

This document describes the bounded public contract for parser-facing
downstreams.

It separates:
- what is implemented now
- what still requires downstream release hygiene

## Contract Shape

The intended public flow is:

```text
canonical text -> parse -> IR -> signals
```

The meaning of each step is:
- `canonical text`: normalized text substrate suitable for one parser spine
- `parse`: deterministic parse and structural extraction over canonical text
- `IR`: typed intermediate representation derived from parsed structure
- `signals`: bounded interaction or extraction signals derived from IR

This flow is descriptive of the parser/evidence boundary only. It is not route
authority for downstream applications.

## Implemented Public Surface

Implemented now:
- `sensiblaw.interfaces.build_canonical_conversation_text(...)`
- `sensiblaw.interfaces.parse_canonical_text(...)`
- `sensiblaw.interfaces.collect_canonical_operational_structure_occurrences(...)`
- `sensiblaw.interfaces.collect_canonical_relational_bundle(...)`
- canonical token/span helpers exported through `sensiblaw.interfaces`

These functions already support the first half of the public contract:

```text
canonical text -> parse
```

and part of the structural evidence substrate that later IR/signals layers can
consume.

## Implemented IR And Signals Surface

Implemented in this checkout:
- `sensiblaw.interfaces.ir_types`
- `sensiblaw.interfaces.ir_adapter`
- `sensiblaw.interfaces.signals`

Implemented public types:
- `InteractionMode`
- `InteractionProjectionReceipt`
- `QueryNode`
- `QueryEdge`
- `QueryTree`
- `SignalSpan`
- `SignalAtom`
- `SignalState`

Implemented public helpers:
- `build_query_tree(...)`
- `project_interaction_mode(...)`
- `extract_interaction_signals(...)`
- `collect_signal_state(...)`
- `summarize_signal_state(...)`

These names are importable through `sensiblaw.interfaces` in this checkout.

## Release Hygiene

The IR/signals modules are now present locally, but downstreams that need to run
across mixed SHAs or pre-export environments should still feature-detect them
until their deployment baseline guarantees these exports.

## Downstream Usage Rule

Mirror-like downstreams may import:
- canonical text adapter helpers
- parser adapter helpers
- shared reducer types and extraction helpers
- `ir_types`, `ir_adapter`, and `signals` modules through
  `sensiblaw.interfaces`

Mirror-like downstreams must keep local:
- channel shaping
- admissibility policy
- route policy
- execution authority

## Non-Goals

This interface does not define:
- Telegram or channel policy
- route enums or route functions
- product execution behavior
- renderer fallback policy

Those remain downstream concerns even after IR/signals modules land.

## Public Import Guidance

Preferred imports:

```python
from sensiblaw.interfaces import (
    build_canonical_conversation_text,
    collect_canonical_relational_bundle,
    parse_canonical_text,
)
```

The public import path should be through `sensiblaw.interfaces`, not through
private implementation modules.

## Status Note

At the time of this document:
- parser adapter exports are live
- shared reducer exports are live
- IR types, IR adapter, and signals exports are live in this checkout

Downstreams should still feature-detect the newer IR/signals imports when they
must support older or mixed revisions that may predate these exports.
