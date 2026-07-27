# Document-graph execution

## Objective

The runtime objective is **minimum time to one committed document**, not balanced
throughput across a tranche. One active document receives the complete bounded
worker budget until its document-local semantic state reaches a certified fixed
point and is committed transactionally.

The semantic object is the document graph. Stages and fibres are execution
constructs only.

## Core state

A useful abstract state is:

```text
G_t = (S_t, P_t, C_t, D_t)
```

where:

- `S_t` is the structural carrier: canonical offsets, sentences, tokens and
  parser observations;
- `P_t` is the current proposal and PNF-factor state;
- `C_t` is the constraint, assessment and refinement state;
- `D_t` is the unresolved-demand frontier.

A worker applies a bounded operator to one operator-specific fibre and returns an
immutable delta:

```text
Delta_i = F_i(G_t, fibre_i)
```

The document state advances through deterministic keyed reduction:

```text
G_(t+1) = G_t join Delta_1 join ... join Delta_n
```

The join must be deterministic and idempotent under replay. Monotone additions
are preferred; refinements must be revision-bound.

## Invariants

1. **One semantic object**
   - The document graph owns global identity, coordinates, factors, constraints,
     demands and the final digest.
   - A fibre never owns an independent semantic graph.

2. **Operator-specific fibres**
   - Initial fibres may be character, sentence or token ranges.
   - Later fibres may be recurrence classes, factor families,
     constraint-connected components, dirty dependency regions or unresolved
     demand cones.
   - Parser fibres are not the permanent graph topology.

3. **One bounded worker budget**

   ```text
   active parser workers
   + active mention workers
   + active projection workers
   + active closure workers
   <= document worker budget
   ```

   Independent nested pools do not satisfy this invariant.

4. **Logical authority is not a serial merge thread**
   - Document authority remains singular.
   - Physical reduction may be partitioned by stable graph keys.
   - The coordinator retains coverage barriers, cross-partition routing,
     fixed-point detection, final digest and commit authority.

5. **No repeated structural derivation**
   - Downstream operators consume the canonical parser carrier.
   - They must not re-tokenise, re-segment or establish a second offset system.

6. **No anonymous throughput**
   - Receipts identify units, worker allocation, partition sizes, process
     evidence, worker compute time, owner merge time and semantic yield.
   - `partition_count > 1` is not proof of parallel execution.

7. **Commit once**
   - Durable visibility occurs through one document transaction after local
     fixed-point certification.

## Scheduling model

The destination is a document-scoped worklist solver rather than a batch stage
pipeline.

A schedulable job contains:

```text
operator
required input keys
owned output keys
unresolved demand or dirty key
estimated cost
expected semantic yield
```

Priority should favour work that:

1. lies on the current document's critical dependency path;
2. discharges a blocking residual or demand;
3. unlocks additional graph work;
4. has high semantic yield per estimated cost;
5. touches a bounded low-contention region.

Worker utilisation is evidence, not the objective. Four busy workers are not
optimal when three are executing speculative work while one closure-critical
job blocks commit.

## Real barriers

Only these barriers should remain broad:

- enough structural-carrier readiness to interpret global coordinates;
- explicit boundary reconciliation;
- document coverage for global recurrence or completeness claims;
- fixed-point certification;
- transactional commit.

Stage names organise receipts and semantic responsibility. They must not create
execution barriers where dependency readiness permits streaming.

## Fixed-point condition

The document-local fixed point is reached only when:

```text
ready queue is empty
and dirty keys are empty
and in-flight jobs are empty
and no locally satisfiable unresolved demands remain
and required coverage barriers are complete
```

External or cross-document demands remain explicit residuals and do not block a
bounded document-local commit.

## Implemented execution cuts

### Mention licensing

`src/policy/document_graph_mentions.py` splits the canonical token carrier into
bounded token fibres:

```text
canonical token carrier + parser sentence observations
  -> process-local lexical/suppression/name/eventuality deltas
  -> deterministic token-interval normalization
  -> license-priority reduction
  -> stable document mention identities
  -> one mention-licensing carrier
```

Canonical tokens remain authoritative for lexical admission and suppression.
Every parser token in each owned sentence is scanned separately for numeric and
eventuality evidence, including parser spans that do not exactly match one
canonical token. Proper-name runs remain sentence-local. The owner alone
normalizes intervals, selects the primary generation reason, creates mention and
license references, and computes the carrier digest.

The execution receipt records requested/granted/peak workers, per-partition token
ranges, worker PIDs and wall intervals, worker compute time, owner merge time,
semantic counts, fingerprints and budget compliance.

### Relational projection

`src/policy/document_graph_projection.py` removes the immediate relational
projection collapse for operational compilation:

```text
one merged parsed document
  -> contiguous parsed-sentence partitions
  -> process-local relational deltas with global coordinates
  -> deterministic atom/relation re-identification
  -> one document relational bundle
```

Properties of this cut:

- workers receive only their sentence partition text and parser observations;
- no worker invokes a second parser boundary;
- local atom and relation identifiers are non-authoritative;
- the owner merges by canonical structural and role keys;
- document-global first-question behaviour remains compatible with the legacy
  reducer;
- the receipt records requested/granted/peak workers, worker PIDs and wall
  intervals, partition sizes, worker compute time, merge time, semantic units,
  fingerprints and the worker-budget invariant.

### Import-order-stable operational routing

The complete tranche runner imports the stable compiler before the PostgreSQL
operational compiler. A package `__getattr__` hook therefore cannot reliably
select graph execution.

`src/policy/corpus_compilation_proxy.py` installs one public module proxy after
the stable module and graph bridge are loaded. Direct imports, package imports
and the runner's legacy-first import order all receive the same graph-enabled
surface. Ordinary reads and monkeypatches forward to the stable compiler module;
only mention licensing, semantic projection and graph contract fields are local
overrides.

`src/policy/graph_optimal_corpus_compilation.py` connects those overrides to the
existing operational compiler without copying the full compiler implementation.
The semantic-layer collector override is lock-guarded and assumes the tranche
invariant of one active document.

### Parity tests

Focused tests cover:

- exact serial/parallel mention-carrier equality;
- non-canonical-token-aligned parser evidence;
- exact serial/parallel relational payload equality;
- deterministic relational output for worker budgets 1, 2 and 4;
- bounded worker receipts and partition progress;
- the tranche runner's actual legacy-first import order;
- proxy forwarding of existing compiler monkeypatches.

## Deliberate limitations

These cuts do **not** yet claim complete graph-optimal execution:

- parser results are still fully merged before mention and projection jobs begin;
- mention and projection each create a stage-scoped process executor rather than
  leasing one persistent executor for the complete document;
- recurrence and form derivation remain document-owner operations;
- closure still uses its existing executor;
- constraint assessment/refinement is not yet a differential dirty-key loop;
- keyed reducer ownership is still logically represented by the document owner;
- useful end-to-end speedup has not yet been accepted by benchmark receipts.

These limitations are recorded rather than hidden by calling the implementation
"fully parallel".

## Next implementation cuts

1. Retain one process executor for the active document and lease it across
   operators.
2. Admit validated parser sentence deltas incrementally instead of waiting for
   whole-document parser merge.
3. Fuse local parser-token projection, mention candidate generation, syntactic
   relation projection and provenance attachment when they share the same input
   carrier and readiness condition.
4. Keep overlap suppression, recurrence, reference candidates, constraint
   assessment and closure as distinct demand-driven operators.
5. Partition deterministic reducers by stable graph keys and route only affected
   dirty keys.
6. Replace whole-graph constraint passes with dependency-indexed differential
   work.
7. Benchmark representative documents with worker budgets 1 and 4; accept each
   parallel operator only when semantic fingerprints match and end-to-end
   document wall time improves.

## Acceptance evidence

A parallel operator is accepted only with receipts showing:

- requested and granted workers;
- peak simultaneously active workers;
- worker process identities and wall-clock overlap intervals;
- partition input sizes;
- worker compute and coordinator merge time;
- aggregate and per-worker semantic units;
- `peak_active_workers <= worker_budget`;
- serial and parallel semantic fingerprint parity;
- end-to-end document latency comparison.

The governing principle is:

> Fibres are temporary bounded views over one progressively refined document
> graph; PNF residuals, constraints and unresolved demands determine what work is
> useful next.
