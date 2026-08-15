# Numeric PNF optimisation status

This note separates implemented execution changes from proof and measurement
obligations. It is intentionally narrower than the architecture overview.

## Dependency-head authority

Migration `052_numeric_parser_head_integrity.sql` adds a deferred commit-time
constraint trigger for representation-version 2 parser tokens.

At transaction commit:

- every numeric token must have a numeric head;
- the head must be a representation-version 2 token in the same sentence;
- a self-head is accepted only when the declared head coordinates equal the
  token coordinates;
- a non-self head must have exactly the declared head coordinates.

This prevents a missing non-root head from becoming an authoritative root even
before the Python projection fallback is removed. The Python producer must still
be changed to fail earlier and emit the appropriate boundary-repair obligation.

## Planner bounds

The dynamic-programming candidate count is bounded by `N * W * B`. Retained
planner state is `N * B` only after complete predecessor paths are replaced by
constant-size backpointers.

Exact interface sketches currently contain three growing key sets. Therefore an
end-to-end exact-work statement additionally requires a per-family interface
budget `C`:

```text
candidate-state work = N * W * B
exact key-union work = N * W * 3C
combined work        = N * W * (3C + B)
```

For fixed `W`, `B`, and `C`, the planner is linear in authored region count.
Without a runtime witness for `C`, only candidate count and backpointer-state
claims may be made.

The corresponding proof objects live in:

- `DASHI.Cognition.PNF.BoundedMDLPlanner`;
- `DASHI.Cognition.PNF.BoundedInterfaceSketch`.

## Demand planning

Migration `053_set_based_numeric_pnf_demand_planning.sql` replaces the active
per-demand procedural loop and recursive per-candidate trigger with:

1. normalized numeric demand lookup keys;
2. one set-based join against `semantic_pnf_global_lookup`;
3. target deduplication;
4. bounded ranking per demand;
5. containment-based common-scope and recency validation;
6. one aggregate candidate-count update.

The old recursive function is retained only for migration compatibility and
comparison; its trigger is removed.

## Still open

- remove the Python missing-head-to-self fallback and reject nullable heads when
  loading sentence closure;
- replace copied planner paths with backpointers in the Python runtime;
- introduce a semantically justified exact export budget or a two-stage
  approximate-proposal/exact-verification planner;
- make parent interfaces discharge sibling demands rather than mainly copying
  child exports;
- implement adjacent-sentence and adjacent-paragraph reconciliation;
- validate migrations, real spaCy/PostgreSQL execution, query plans, restart
  identity, document 0008, and synthetic scaling on the self-hosted runner.
