# Numeric PNF optimisation status

This note separates implemented execution changes from proof and measurement
obligations. It is intentionally narrower than the architecture overview. The
priority ordering is defined by
`docs/architecture/PRODUCTION_PERFORMANCE_CONSTITUTION.md`.

## Production priority

The optimization target is not "make every existing path faster". It is:

```text
parse once
→ compile numerically
→ retain proofs
→ reopen locally
→ reuse forever
```

The current order is therefore:

1. keep numeric strict execution as the normal PostgreSQL production route;
2. remove/bypass remaining nonnumeric compatibility carriers;
3. make reverse-dependency reopening the ordinary update path;
4. demonstrate controlled corpus-learning work non-increase;
5. establish token-normalised cold/replay/edit/same-domain scaling;
6. only then parallelise/vectorise the remaining measured numeric kernels.

The rich operational graph remains valuable as an audit/reference/parity oracle.
It is not the desired steady-state production carrier.

## Numeric strict production path

`src/policy/numeric_pnf_compilation.py` has the crucial architectural property:
strict compilation does not reconstruct the legacy document-sized parser
mapping, mention carrier, factor graph, or artifact bundle. spaCy commits numeric
observations once and PNF closure proceeds over those rows.

`src/policy/streaming_spacy_parser_execution.py` now treats PostgreSQL authority
plus an omitted execution strategy as an explicit production choice:

```text
postgresql-typed-exact-execution:v2
```

Explicit `local-compatibility-replay` remains authoritative for audit/parity and
no-database callers retain compatibility behavior. The default can also be
rolled back deliberately with `SENSIBLAW_NUMERIC_PRODUCTION_DEFAULT=0`; there is
no silent fallback from a requested strict run.

## Native demand occurrence provenance is already numeric

Migration `135_demand_trigger_target_occurrence.sql` closes the previously
suspected operational-provenance blocker directly on the numeric carrier.

An `AFTER INSERT OR UPDATE` producer on `execution.semantic_pnf_demand` records:

- occurrence role 1: the exact factor/token trigger;
- occurrence role 2: the exact typed target token/object when uniquely licensed;
- occurrence role 3: other exact factor-support evidence tokens.

The producer uses numeric factor-token support, object-token support and typed
hyperedges. It fails closed when the producer factor or target is ambiguous and
never searches for a nearby noun/object. Missing target provenance therefore
remains unresolved and cannot authorize H9 work.

The older operational→numeric occurrence bridge remains useful for replay and
migration of historical operational demands; it is not a dependency of
`numeric_pnf_compilation.py`.

## H3 → H6 → H9 is physically residual-driven

Migration `110_residual_driven_h6_and_zero_need_h9.sql` and the existing consumer
runtime already distinguish queue processing from semantic stopping:

```text
H3 completed
→ rebuild consumer outcome
→ enqueue H6 only when residual_required

H6 ready residual
→ produce numeric typed discourse/temporal evidence
→ rebuild outcome
→ expose H9 only when residual_required

H9 residual
→ explicit consumer world-axis need
→ cache/provider request planning
```

Missing H6 relations create no negative evidence. Zero explicit H9 needs is a
successful zero-work plan.

`src/storage/postgres/progressive_horizon_runtime_store.py` now exposes this as a
single production-facing orchestration contract. H6 is not called when the H3
residual is empty; H9 planning is not called when the H6 residual is empty; H9
planning requires explicit opt-in and never performs provider I/O.

The remaining horizon work is therefore not "make the logical labels lazy" but
validate this residual-only route at corpus scale and make consumer
reverse-dependency wakeup the normal incremental entrypoint.

## JSON / rich carrier status

JSON is not a numeric execution optimization target. It is sin-binned from
semantic authority and ordinary hot execution.

A canonical JSON pass is tolerated only where an existing versioned identity
contract is explicitly defined over those bytes. The current work-conserving
manifest optimization makes this a named legacy boundary capability, reuses the
producer digest/seal, and bypasses repeated envelope reconstruction for
same-process immutable consumers.

The target remains:

```text
JSON transformations in ordinary semantic execution ≈ 0
```

See `docs/architecture/JSON_SIN_BIN.md` and
`src/runtime/numeric_hot_path_constitution.py`.

## Performance constitution

`src/runtime/performance_constitution.py` encodes two important restrictions on
performance claims:

- `T_post-parser <= 0.10 * T_spaCy` may be certified only when both parser and
  post-parser kernels are explicitly measured; wall subtraction is not accepted;
- `W_after <= W_before` may be certified only for exact controlled
  workload/configuration identity with measured semantic work units.

A single cold run cannot establish incremental economy, delta-locality,
same-domain reuse, or corpus-scale linearity.

## Recent compatibility-path physical result

The work-conserving compatibility path remains useful for migration/parity and
has materially improved:

- strict semantic acceptance/digest parity has been preserved;
- physical PostgreSQL stage fan-out on the medium replay fell from 97 to 11;
- observed wall time fell from 112.64s to a repeated roughly 72–79s range;
- transaction commit/fsync tail was only milliseconds;
- COPY tuple expansion/stage setup were ruled out as dominant costs.

Those wins are important, but they do not change the production priority: once a
cost belongs only to a compatibility carrier that numeric production bypasses,
removing the carrier outranks further micro-optimizing it.

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

### Highest-priority production work

- prove in live PostgreSQL that the new numeric-default entrypoint exercises the
  expected migration 135 occurrence producer and residual-only horizon route;
- make consumer reverse-dependency wakeup the ordinary update/reopen entrypoint,
  not an optional store method;
- remove remaining semantic JSON/string/regex paths rather than merely bypassing
  them at runtime;
- produce controlled cold/exact-replay/small-edit/same-domain-new-document
  measurements with explicit parser and post-parser timings;
- demonstrate `W_after <= W_before` on exact controlled recurring workloads;
- identify any consumer output that still genuinely requires operational
  compatibility and either port that producer to numeric authority or document
  why it is an explicit boundary/audit concern.

### Numeric planner/runtime work

- remove the Python missing-head-to-self fallback and reject nullable heads when
  loading sentence closure;
- replace copied planner paths with backpointers in the Python runtime;
- introduce a semantically justified exact export budget or a two-stage
  approximate-proposal/exact-verification planner;
- make parent interfaces discharge sibling demands rather than mainly copying
  child exports;
- implement adjacent-sentence and adjacent-paragraph reconciliation where H6
  evidence requires it;
- validate migrations, real spaCy/PostgreSQL execution, query plans, restart
  identity, document 0008, and synthetic scaling on the self-hosted runner.

### Later physical optimizations

- dependency-correct frozen owner waves with exact reverse-dependency wakeup;
- SIMD/native integer kernels for measured intersections, masks, packed address
  decode, and frontier propagation;
- partitioning only when measured table/index working sets justify it.
