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
- `production_compact` retains semantic state and compact references, but not
  completed execution generations;
- `benchmark_verified` retains the evidence needed for serial/parallel parity
  without defaulting to the complete audit ledger.

## Bounded owner

`BoundedStreamingSemanticOwner` is a parity surface over the canonical
`StreamingSemanticOwner`. It adds:

- `OwnerKey -> proposal` buckets;
- an incremental known-factor dependency set;
- compact operator job payloads;
- compact receipt references;
- explicit release of completed jobs, full receipts, and state deltas;
- retention and compaction receipts.

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
unbounded generation.

## Current integration boundary

This PR establishes and tests the resource contract and bounded owner in
isolation. It deliberately does not yet replace the canonical PostgreSQL
compiler path. The next integration step is to route the streaming-closure
stage through the bounded owner and scheduler after parity tests pass, then add
single-document document-0008 acceptance with retained pressure and RSS
receipts.

The order is intentional:

1. prove owner reduction parity;
2. prove pressure relief and bounded stopping;
3. route one stage through the bounded path;
4. run document 0008 under a soft limit;
5. only then expand to a persistent document-wide process pool and incremental
   private persistence.
