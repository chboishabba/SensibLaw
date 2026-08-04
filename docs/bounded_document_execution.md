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

## Bounded frontier admission

The scheduler must not wait for a complete document frontier. Sentence-local
observation deltas are admitted in bounded batches; each batch activates its
ready closure jobs and drains them before the next batch is admitted. This
keeps the ready frontier bounded and makes the first lease observable before
the full document has been traversed.

Coverage completion is indexed by `(scope_ref, barrier)`. Admission therefore
does not scan every prior coverage notice for each incoming delta. Production
retention does not duplicate full delta payloads into completed job history;
the canonical observation artifact remains available for fibred projection and
persistence.

The existing `streaming_closure` stage remains the sole named lifecycle stage.
It reports `current_kernel` as diagnostic context and publishes deltas
admitted, ready jobs, leases, retained observations, RSS, and completion
counters through its declared measures.

## Canonical compiler integration

Parser fibres write two atomic execution artifacts: the reusable parse
checkpoint and a compact summary/receipt. The parent constructs its document
receipt from summaries only; it does not reload every parse payload. At each
fibre completion it samples process-tree RSS. A lost parser process is treated
as a terminal resource event, writing a `parser_fibre_execution` receipt with
the active fibre and reusable checkpoint references before raising
`DocumentResourceLimitError`. It never silently retries with smaller fibres.

Bounded execution is installed as an execution strategy on
`src.policy.operational_corpus_compilation`. It does not introduce another
compiler authority. The existing `_streaming_semantic_build` function remains
available as `_serial_streaming_semantic_build` for parity diagnosis.

The bounded strategy now controls `streaming_closure`:

1. parser observation deltas enter the indexed owner;
2. base proposals reduce through owner-key buckets;
3. sentence-local deltas enter bounded admission batches rather than one
   complete ready frontier;
4. the scheduler leases each ready batch at the configured in-flight limit;
5. each receipt is admitted and its dirty group reduced immediately;
6. completed full jobs and receipts are released in production mode;
7. RSS, process-tree RSS, pending jobs, in-flight jobs, dirty groups, retained
   observations, and
   retention counts are emitted through the named stage callback;
8. fixed-point certification and outward artifacts retain the existing
   canonical contracts.

This is a bounded closure executor, not yet the final persistent document-wide
process pool. Parser, mention, projection, closure, and persistence do not yet
share one executor.

## Manifest-backed document publication

The document-fibre ownership intervals also define immutable projection
partitions.  A partition stores only owned parser observations, annotation and
relation record references, layer-segment references, and explicit boundary
demands.  It is reusable only for an exact document source digest, structural
carrier, interval, parser/reducer contract, and build key.

`document_projection_join` is the sole semantic boundary.  It verifies ordered
contiguous coverage, exact-once owned annotation coordinates, matching build
identity, and boundary-demand references before it emits the document manifest.
The existing document-level typing, reduction, closure, PNF and demand work
then runs once; partitions never independently publish a semantic document.

Logical layer manifests are ordered immutable annotation-record references, so
their `layer_ref` and the ref-only `AnnotationGraph` identity do not depend on
partition scheduling.

Production artifact projection is manifest-backed.  The existing artifact keys
remain stable, but their values are versioned descriptors containing the
representation, manifest/root reference, ordered digest, record count, and
reader contract.  Whole-layer and whole-graph dictionaries are available only
through the explicitly injected materialised compatibility policy.  Partition
size and scheduling never select this policy.

The parser-to-projection handoff is a replayable owned-sentence carrier, not a
merged document dictionary.  Each physical parse is checkpointed, then released
from the parent process.  Consumers may re-iterate the carrier; each iteration
loads one owned fibre at a time, assigns the same canonical global token and
dependency coordinates, and releases that fibre before advancing.  This is an
execution representation only: it preserves the one document-level parser
observation stream and does not give fibres semantic authority.

The compiler streams immutable record families in bounded batches.  Annotation
records use the existing `language` schema; factors and constraints use
`algebra`; graph membership uses `pnf`; refinements and demands use
`resolution`.  Migration `025_document_projection_manifests` stores only
execution/build metadata in `execution`; it does not create another
authoritative public compiler schema.

Publication order is normative:

1. persist or exactly reuse immutable projection partitions;
2. validate exact coverage, duplicate ownership, and boundary demands;
3. run the sole document join and document fixed point;
4. stream semantic record families and verify their ordered digests;
5. insert the completed document manifest/build and mark the occurrence
   compiled in one transaction.

A failure or bounded resource stop before step 5 leaves no published document.
Persisted partitions are execution evidence and may be reused only when source
hash, carrier, owner/context intervals, parser contract, reducer/projection
contract, and build key all match.

Overlap is never silently accepted.  Every overlap observation must either map
to exactly one owned record or produce an explicit boundary demand.

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
SENSIBLAW_DOCUMENT_FRONTIER_BATCH_SIZE=32
SENSIBLAW_DOCUMENT_COMPACTION_ATTEMPTS=3
SENSIBLAW_DOCUMENT_MINIMUM_RECOVERY_MIB=64
SENSIBLAW_RESOURCE_CHECKPOINT_DIR=/tmp/sensiblaw-resource-checkpoints
```

The checkpoint directory is optional. When configured, pressure checkpoints are
written atomically as JSON. A bounded stop retains pending and in-flight job
references, completed-signature count, resource measurements, and retention
counts.

## Remaining integration order

1. validate bounded frontier admission, focused compiler, fibred projection,
   and import-order parity;
2. run reduced document-0008 smoke work and require visible leasing;
3. extend the same resource and progress contract through named
   `artifact_projection`, `postgres_persistence`, and `document_publication`
   kernels before rerunning document 0008 under 512 MiB soft and 576 MiB hard
   limits;
4. retain the document-0008 stage/resource ledger and pressure checkpoint, if
   any;
5. replace the closure thread pool with the persistent active-document process
   pool after worker payloads are proven serialisable and bounded;
6. move constraint/refinement work onto differential dirty-key jobs;
7. validate strict 12k and full document 0008 with bounded batch/release
   resource receipts and a plateau or saw-tooth memory profile;
8. only then restart the complete tranche.
