# Numeric PNF optimisation status

This note separates implemented execution changes from proof and measurement
obligations. It is intentionally narrower than the architecture overview. The
priority ordering is defined by
`docs/architecture/PRODUCTION_PERFORMANCE_CONSTITUTION.md`.

## Production target

```text
parse once
→ compile numerically
→ retain proofs
→ reopen locally
→ reuse forever
```

The rich operational graph remains an audit/reference/parity oracle. It is not
the desired steady-state production carrier.

The current priority is therefore:

1. keep numeric strict execution as the normal PostgreSQL production route;
2. remove/bypass remaining nonnumeric compatibility carriers;
3. validate sparse reopening and residual horizons on live PostgreSQL;
4. measure controlled corpus-learning and token-normalised scaling without making
   observability itself part of the production tax;
5. only then parallelise/vectorise the remaining measured numeric kernels.

## Numeric strict production path

`src/policy/numeric_pnf_compilation.py` does not reconstruct the legacy
document-sized parser mapping, mention carrier, factor graph, or artifact bundle.
spaCy commits numeric observations once and PNF closure proceeds over those rows.

`src/policy/streaming_spacy_parser_execution.py` treats PostgreSQL authority plus
an omitted execution strategy as the production choice:

```text
postgresql-typed-exact-execution:v2
```

Explicit `local-compatibility-replay` remains authoritative for audit/parity and
no-database callers retain compatibility behavior. The default can be rolled
back deliberately with `SENSIBLAW_NUMERIC_PRODUCTION_DEFAULT=0`; there is no
silent fallback from a requested strict run.

## Native demand occurrence provenance is numeric

Migration `135_demand_trigger_target_occurrence.sql` supplies trigger, target and
evidence occurrence provenance directly on the numeric demand carrier.

Its producer uses numeric factor-token support, object-token support and typed
hyperedges. It fails closed when the producer factor or target is ambiguous and
never searches for a nearby noun/object. Missing target provenance remains
unresolved and cannot authorize H9 work.

The older operational→numeric occurrence bridge remains useful for historical
replay/migration; it is not a dependency of `numeric_pnf_compilation.py`.

## H3 → H6 → H9 is physically residual-driven

Migration `110_residual_driven_h6_and_zero_need_h9.sql` distinguishes queue
processing from semantic stopping:

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

`src/storage/postgres/progressive_horizon_runtime_store.py` exposes this ordering
as one production-facing operation. H6 is not called when the H3 residual is
empty; H9 planning is not called when the H6 residual is empty; H9 planning is
explicit and never performs provider I/O itself.

## Reverse-dependency reopening is now ordinary evidence execution

Migration `091_numeric_incremental_wiring.sql` already made evidence insertion
wake the global sparse incremental queue.

Migration `139_consumer_incremental_evidence_wakeup.sql` completes the consumer
lane. New evidence now reopens only consumer/query fibres that explicitly
registered a dependency on the evidence atom's numeric coordinates:

```text
6 -> evidence_id
4 -> source_region_id
5 -> source_interface_id
```

No document/corpus scan is performed. No proof/admissibility relation is mutated.
A missing dependency creates zero work, not negative evidence.

This means the ordinary update shape is now substantially closer to:

```text
Δ evidence
→ sparse reverse dependencies
→ affected consumer fibres
→ only the minimum required horizon
```

rather than document-wide recomputation.

## Production staging overhead

Migration `138_drop_unused_persistence_stage_document_index.sql` removes the
historical `(document_ref, build_key_sha256)` B-tree from the UNLOGGED staging
carrier. Live replay instrumentation observed zero scans of that index while its
maintenance charged every provisional staging row. Retry/publication continue to
use deterministic `stage_ref` and the stage/kind authority index.

This is intentionally an execution-only optimization; semantic authority is
unchanged.

## JSON / text / regex status

JSON is not a numeric execution optimization target. It is sin-binned from
semantic authority and ordinary hot execution.

A canonical JSON pass is tolerated only where an existing versioned identity
contract is explicitly defined over those bytes. The current work-conserving
manifest optimization makes this a named legacy boundary capability and reuses
the producer digest/seal rather than repeatedly reconstructing envelopes.

The target remains:

```text
JSON transformations in ordinary semantic execution ≈ 0
```

The same presumption applies to semantic string matching and regex after spaCy.
Permitted text/JSON/regex use must identify an ingestion, external protocol,
export/audit, parser-adapter, or legacy-identity boundary. See
`docs/architecture/JSON_SIN_BIN.md` and
`src/runtime/numeric_hot_path_constitution.py`.

## Performance claims and observability

`src/runtime/performance_constitution.py` prevents two common false claims:

- `T_post-parser <= 0.10 * T_spaCy` can be certified only when both parser and
  post-parser kernels are explicitly measured; wall subtraction is not a parser
  measurement;
- `W_after <= W_before` can be certified only for exact controlled
  workload/configuration identity with measured semantic work units.

A single cold run cannot establish incremental economy, delta-locality,
same-domain reuse, or corpus-scale linearity.

The controlled corpus-learning SQL intentionally scans several numeric
relations: token/object/factor counts, unresolved demand funnel, cross-document
lexical reuse, entity/world cache reuse, and stage receipts. It is therefore an
**observatory**, not an ordinary compiler obligation.

Fresh numeric compilation records this controlled observation only when:

```text
SENSIBLAW_RECORD_CONTROLLED_REUSE=1
```

Ordinary production defaults to zero cost for that scan. Cached numeric reuse
never masquerades as a fresh semantic-work observation; it records
`reused_numeric_pnf` and belongs to the exact-replay benchmark.

The four experiments remain deliberately distinct:

```text
T_cold                  fresh numeric compile
T_exact-replay          cached build/reopen
T_small-edit            sparse dependency reopen after Δ input/evidence
T_same-domain-new-doc   new source with accumulated corpus caches
```

Tokens are the canonical cross-document denominator. The desired reports include
work/token, elapsed/token, peak memory/token, tokens/s, parser/post-parser ratio,
new versus reused work, H3/H6/H9 residual fractions, reopened fibres and provider
calls.

## Recent compatibility-path physical result

The work-conserving compatibility path remains useful for migration/parity and
has materially improved:

- strict semantic acceptance/digest parity has been preserved;
- physical PostgreSQL stage fan-out on the medium replay fell from 97 to 11;
- observed wall time fell from 112.64s to a repeated roughly 72–79s range;
- transaction commit/fsync tail was only milliseconds;
- COPY tuple expansion/stage setup were ruled out as dominant costs.

Those wins do not change production priority: once a cost belongs only to a
compatibility carrier that numeric production bypasses, removing the carrier
outranks further micro-optimizing it.

## Dependency-head authority

Migration `052_numeric_parser_head_integrity.sql` adds deferred commit-time
integrity for representation-version 2 dependency heads. Every numeric token
must have a same-sentence numeric head and self-head coordinates must agree with
the token itself.

The remaining producer-side task is to remove any Python missing-head-to-self
fallback so an invalid non-root head fails at the producer boundary instead of
being repaired into false root structure.

## Planner bounds

The dynamic-programming candidate count is bounded by `N * W * B`. Retained
planner state is `N * B` only after complete predecessor paths are represented by
constant-size backpointers.

Exact interface sketches currently contain three growing key sets. An end-to-end
exact-work statement therefore additionally requires a per-family interface
budget `C`:

```text
candidate-state work = N * W * B
exact key-union work = N * W * 3C
combined work        = N * W * (3C + B)
```

For fixed `W`, `B`, and `C`, the planner is linear in authored region count.
Without a runtime witness for `C`, only candidate-count and backpointer-state
claims may be made.

The corresponding proof objects live in:

- `DASHI.Cognition.PNF.BoundedMDLPlanner`;
- `DASHI.Cognition.PNF.BoundedInterfaceSketch`.

## Demand planning

Migration `053_set_based_numeric_pnf_demand_planning.sql` replaces the active
per-demand procedural loop and recursive per-candidate trigger with one bounded
set-based numeric lookup/ranking pass. The old recursive function is retained
only for migration compatibility/comparison; its trigger is removed.

## Still open

### Highest-priority production work

- apply/validate the current migrations on live PostgreSQL and prove the numeric
  default exercises migration 135, residual-only H3/H6/H9 and migration 139;
- identify and remove remaining semantic JSON/string/regex paths after spaCy;
- produce controlled cold/exact-replay/small-edit/same-domain-new-document
  measurements with explicit parser and post-parser timing;
- demonstrate `W_after <= W_before` on exact controlled recurring workloads;
- identify any output that still genuinely requires operational compatibility and
  either port the producer to numeric authority or defend it as an explicit
  audit/boundary concern.

### Numeric planner/runtime work

- remove the Python missing-head-to-self fallback;
- replace copied planner paths with backpointers where still present;
- introduce a semantically justified exact export budget or a two-stage
  approximate-proposal/exact-verification planner;
- make parent interfaces discharge sibling demands rather than mainly copying
  child exports;
- validate adjacent-sentence/paragraph H6 evidence and exact sparse fanout;
- validate real spaCy/PostgreSQL execution, query plans, restart identity,
  document 0008, and synthetic scaling on the self-hosted corpus.

### Later physical optimizations

- dependency-correct frozen owner waves with exact reverse-dependency wakeup;
- SIMD/native integer kernels for measured intersections, masks, packed address
  decode, and frontier propagation;
- partitioning only when measured table/index working sets justify it.
