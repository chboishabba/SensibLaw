# Bounded document execution

This document specifies the first bounded-memory execution slice for large PNF
documents. It changes execution and retention only; semantic authority remains
with the canonical document compiler and PNF algebra.

## Pressure is backpressure before failure

Crossing the soft memory limit does not immediately fail a document. The active
document transitions through this control loop:

```text
normal
  -> throttle/defer producer jobs
  -> prioritise reducer, closure-consumer, and persistence work
  -> compact diagnostic-only retained history
  -> checkpoint the pressure receipt
  -> resample memory
  -> resume producers after the recovery target is crossed
```

The scheduler declares `bounded_stop` only when all of the following hold:

1. RSS or process-tree RSS is at or above the hard limit;
2. the configured compaction attempts have been exhausted;
3. the footprint has not shrunk by the configured minimum recovery amount.

A bounded stop is checkpointable and fail-closed:

```text
resource_limit_reached=true
state=bounded_stop
checkpoint_retained=true
```

It is distinct from an OOM kill and from a temporary producer pause.

## Hysteresis

The soft limit starts pressure relief. Producer work resumes only after memory
falls below a lower recovery target, by default 90% of the soft limit. This
prevents repeated start/stop oscillation around one threshold.

## Execution and retention are independent

`DocumentExecutionPolicy` controls:

- total worker budget;
- maximum in-flight jobs;
- queue byte bound;
- soft and hard memory limits;
- recovery target;
- compaction attempts;
- minimum required shrinkage;
- producer leases while under pressure.

`DocumentRetentionPolicy` controls whether execution history remains in RAM:

- `audit_full` retains jobs, full receipts, state deltas, and observation bodies;
- `production_compact` retains semantic state and compact derivation records,
  but not completed execution generations or duplicated proposal bodies;
- `benchmark_verified` retains the evidence needed for serial/parallel parity
  without defaulting to the complete audit ledger.

## Bounded owner

`BoundedStreamingSemanticOwner` is a parity surface over the canonical
`StreamingSemanticOwner`. It adds:

- `OwnerKey -> proposal` buckets;
- an incremental known-factor dependency set;
- compact operator job payloads;
- compact reference-only job and receipt rows for provenance;
- explicit release of completed jobs, full receipts, and state deltas;
- retention and compaction receipts.

The compact records preserve the fibred derivation and integrated-producer
contracts. They do not retain parser observation bodies or proposal objects a
second time.

The owner still returns immutable state deltas and uses the existing canonical
proposal reducer. It does not mutate a shared graph and does not promote legal
truth or identity.

## Bounded scheduler

`BoundedDocumentScheduler` accepts one persistent executor. Workers are not
assigned permanently to stages. Any free worker leases the highest-priority
ready job, subject to the active document budget.

Work is classified as:

- structural producer;
- semantic producer;
- reducer;
- closure consumer;
- persistence consumer.

When memory or queued output is high, producer leases become zero while
consumers continue. This drains retained work instead of producing another
unbounded generation. An `on_lease` callback moves semantic jobs from pending
to in-flight only when a worker actually receives them.

## Canonical compiler integration

Bounded execution is installed as an execution strategy on
`src.policy.operational_corpus_compilation`. It does not introduce another
compiler authority. The existing `_streaming_semantic_build` function remains
available as `_serial_streaming_semantic_build` for parity diagnosis.

The bounded strategy now controls `streaming_closure`:

1. parser observation deltas enter the indexed owner;
2. base proposals reduce through owner-key buckets;
3. closure jobs enter one bounded ready frontier;
4. the scheduler leases at most the configured in-flight limit;
5. each receipt is admitted and its dirty group reduced immediately;
6. completed full jobs and receipts are released in production mode;
7. RSS, process-tree RSS, pending jobs, in-flight jobs, dirty groups, and
   retention counts are emitted through the named stage callback;
8. fixed-point certification and outward artifacts retain the existing
   canonical contracts.

This is a bounded closure executor, not yet the final persistent document-wide
process pool. Parser, mention, projection, closure, and persistence do not yet
share one executor.

## Configuration

Bounded execution is enabled by default. Set
`SENSIBLAW_BOUNDED_DOCUMENT_EXECUTION=0` for serial/parity diagnosis.

The operator-facing controls are:

```text
SENSIBLAW_DOCUMENT_RETENTION_MODE=production_compact
SENSIBLAW_DOCUMENT_SOFT_MEMORY_MIB=5120
SENSIBLAW_DOCUMENT_HARD_MEMORY_MIB=6144
SENSIBLAW_DOCUMENT_RECOVERY_MEMORY_MIB=4608
SENSIBLAW_DOCUMENT_QUEUE_LIMIT_MIB=64
SENSIBLAW_DOCUMENT_MAX_IN_FLIGHT=8
SENSIBLAW_DOCUMENT_COMPACTION_ATTEMPTS=3
SENSIBLAW_DOCUMENT_MINIMUM_RECOVERY_MIB=64
SENSIBLAW_RESOURCE_CHECKPOINT_DIR=/tmp/sensiblaw-resource-checkpoints
```

The checkpoint directory is optional. When configured, pressure checkpoints are
written atomically as JSON. A bounded stop retains pending and in-flight job
references, completed-signature count, resource measurements, and retention
counts.

## Remaining integration order

1. validate focused compiler, fibred projection, and import-order parity;
2. run document 0008 alone under the configured soft and hard limits;
3. retain its stage/resource ledger and pressure checkpoint, if any;
4. replace the closure thread pool with the persistent active-document process
   pool after worker payloads are proven serialisable and bounded;
5. move constraint/refinement work onto differential dirty-key jobs;
6. add incremental private persistence and atomic publication;
7. only then restart the complete tranche.
