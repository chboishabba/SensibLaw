# Numeric PNF optimisation status

This note separates implemented execution changes from proof and measurement
obligations. It is intentionally narrower than the architecture overview.  The
priority ordering is defined by
`docs/architecture/PRODUCTION_PERFORMANCE_CONSTITUTION.md`.

## Production priority

The optimization target is not "make every existing path faster".  It is:

```text
parse once
→ compile numerically
→ retain proofs
→ reopen locally
→ reuse forever
```

Therefore the current priority order is:

1. complete all semantically required outputs directly on the numeric compiler;
2. make numeric strict execution the normal production route;
3. remove/bypass nonnumeric compatibility carriers from that route;
4. make H3→H6→H9 physically lazy and reverse-dependency incremental;
5. demonstrate controlled corpus-learning work non-increase;
6. establish token-normalised cold/replay/edit/same-domain scaling;
7. only then parallelise/vectorise the remaining measured numeric kernels.

The rich operational graph remains valuable as an audit/reference/parity oracle.
It is not the desired steady-state production carrier.

## Numeric strict path already exists

`src/policy/numeric_pnf_compilation.py` already has the crucial architectural
property: strict compilation does not reconstruct the legacy document-sized
parser mapping, mention carrier, factor graph, or artifact bundle.  spaCy commits
numeric observations once and PNF closure proceeds over those rows.

`src/policy/streaming_spacy_parser_execution.py` routes strict PostgreSQL
strategies to this numeric compiler.  The remaining integration question is not
whether the numeric compiler exists, but which producer outputs still force
normal workloads through operational compatibility before downstream consumers
are satisfied.

In particular, occurrence provenance such as trigger/target/evidence coordinates
must be produced natively on the numeric carrier wherever downstream H3/H6/H9
or external admission requires it.  A compatibility bridge is a migration seam,
not the final architecture.

## JSON / rich carrier status

JSON is not a numeric execution optimization target.  It is sin-binned from
semantic authority and ordinary hot execution.

A canonical JSON pass is tolerated only where an existing versioned identity
contract is explicitly defined over those bytes.  The current work-conserving
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

`src/runtime/performance_constitution.py` now encodes two important restrictions
on performance claims:

- `T_post-parser <= 0.10 * T_spaCy` may be certified only when both parser and
  post-parser kernels are explicitly measured; wall subtraction is not accepted;
- `W_after <= W_before` may be certified only for exact controlled
  workload/configuration identity with measured semantic work units.

A single cold run cannot establish incremental economy, delta-locality,
same-domain reuse, or corpus-scale linearity.

## Recent physical execution result

The work-conserving compatibility path remains useful for migration/parity and
has materially improved:

- strict semantic acceptance/digest parity has been preserved;
- physical PostgreSQL stage fan-out on the medium replay fell from 97 to 11;
- observed wall time fell from 112.64s to a repeated roughly 72–79s range;
- transaction commit/fsync tail was only milliseconds;
- COPY tuple expansion/stage setup were ruled out as dominant costs.

Those wins are important, but they do not change the priority above: once a cost
belongs only to a compatibility carrier that numeric production can bypass,
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

### Production blockers

- identify and port every still-operational-only producer output required by
  numeric downstream consumers, especially exact occurrence provenance;
- make the numeric strict route the preferred/default production entrypoint
  while retaining an explicit compatibility escape hatch;
- remove remaining semantic JSON/string/regex paths rather than merely bypassing
  them at runtime;
- make H3/H6/H9 evidence production physically residual-driven;
- make reverse-dependency reopening the ordinary update path;
- produce controlled cold/replay/edit/same-domain reuse measurements.

### Numeric planner/runtime work

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

### Later physical optimizations

- dependency-correct frozen owner waves with exact reverse-dependency wakeup;
- SIMD/native integer kernels for measured intersections, masks, packed address
  decode, and frontier propagation;
- partitioning only when measured table/index working sets justify it.
