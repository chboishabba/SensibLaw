# Distributed semantic graph execution

## Status

This document defines the physical execution and persistence contract for large
SensibLaw documents. It does not introduce a second semantic compiler.

The semantic object remains one document graph. Mini, midi, and mega fibres are
physical execution and checkpoint partitions over that graph. PostgreSQL is the
durable authority for distributed scheduling, revision admission, fixed-point
certification, and publication.

Local JSON and JSONL files are transitional debug, export, and emergency-recovery
projections. They are not the authority for multi-machine execution.

## Governing invariant

No stage may require the simultaneous in-memory presence of:

1. its complete input graph;
2. its complete output graph; and
3. the complete serialized representation of either graph.

Each stage consumes bounded references, emits bounded immutable deltas, commits a
durable manifest or cursor, and releases its working set before its successor
starts.

## Storage responsibilities

### PostgreSQL

PostgreSQL owns:

- document and build identities;
- semantic owner revision streams;
- job declarations and dependencies;
- leases, attempts, epochs, and expiries;
- immutable worker deltas and their admissions;
- graph manifests and family segments;
- factor and residual revisions;
- finalisation cursors;
- fixed-point and execution receipts;
- the transactional outbox;
- staged and committed publication builds.

Migration `026_distributed_semantic_execution.sql` creates the `execution`
schema surfaces for this protocol.

### Content-addressed payload storage

Large immutable families may be held in PostgreSQL rows or object segments. A
segment is identified by digest, row count, byte count, encoding contract, and
canonical sequence. PostgreSQL records its identity and availability.

A local filesystem JSONL segment is currently supported as a transitional
transport. The same family descriptor can later point at PostgreSQL or object
storage without changing the graph root identity.

### JSON and JSONL

JSON/JSONL remains appropriate for:

- diagnostic traces;
- portable evidence bundles;
- CI artifacts;
- human inspection;
- failed-run preservation;
- import/export.

A JSONL path by itself is never a distributed lease, owner, cursor, or
publication authority.

## Graph representation

A graph revision is represented as:

\[
G_r=(V_r,E_r,\Delta_r,U_r,C_r),
\]

where:

- \(V_r\) is the content-addressed node family;
- \(E_r\) is the typed edge family;
- \(\Delta_r\) is the accepted revision overlay;
- \(U_r\) is the unresolved frontier;
- \(C_r\) is coverage and certification evidence.

A parent hierarchy node stores:

\[
P=(\operatorname{childRefs},\Delta V,\Delta E,U,C),
\]

not copies of descendant interiors. A parent operation may read child
interfaces, cross-child deltas, and the dirty dependency cone. Reconstructing
all descendant interiors is an explicit export operation, not normal execution.

## Job protocol

A job is a graph transformation:

\[
J=(j,k,I,R,p,a,\tau),
\]

where:

- \(j\) is a stable job identity;
- \(k\) is the semantic owner key;
- \(I\) is the immutable input manifest set;
- \(R\) is the expected owner revision;
- \(p\) is the operation contract;
- \(a\) is attempt and lease state;
- \(\tau\) is scheduling and resource policy.

A worker emits:

\[
\delta J=(\Delta V,\Delta E,\Delta U,\Delta C,\rho).
\]

The worker does not mutate the owner graph. It submits the immutable delta to a
transactional admission protocol.

### Leasing

Workers lease ready rows using canonical priority order and:

```sql
FOR UPDATE SKIP LOCKED
```

A lease increments `lease_epoch`, records `lease_owner`, and receives an expiry.
Long computation renews the same epoch on an independent connection.

### Fencing

A result is admissible only when all of the following still hold:

- the job is `leased`;
- `lease_owner` matches;
- `lease_epoch` matches;
- the owner revision equals `expected_owner_revision`.

A late result from epoch \(e\) cannot be admitted after epoch \(e'>e\) has been
issued.

### Delivery semantics

Execution is at least once. Semantic admission is exactly once.

This is achieved through:

- deterministic job and delta identities;
- unique constraints;
- lease fencing;
- owner-revision compare-and-swap;
- idempotent completed-job acknowledgement;
- immutable output manifests;
- transactional outbox records.

A worker may repeat computation after an acknowledgement failure. PostgreSQL
returns the existing admission rather than advancing the graph twice.

## Logical owner authority

“One owner” means one serializable PostgreSQL revision stream per semantic owner
key, not one Python object.

For owner key \(k\):

\[
r_{k,0}<r_{k,1}<\cdots<r_{k,n}.
\]

Distinct owner keys may advance concurrently unless a declared dependency joins
them. The document graph reconciles those streams through explicit deltas and
fixed-point obligations.

## Fixed point

The database fixed-point predicate is:

\[
\begin{aligned}
\operatorname{Fixed}(d)\iff{}&
\neg\exists j\in J_d:\operatorname{state}(j)\in
\{\text{ready},\text{leased},\text{retryable}\}\\
&\land\neg\exists k\in K_d:\operatorname{dirty}(k)\\
&\land\neg\exists\delta\in\Delta_d:\neg\operatorname{admitted}(\delta)\\
&\land\operatorname{coverageClosed}(d)\\
&\land\operatorname{localObligations}(d)=\varnothing.
\end{aligned}
\]

The certificate binds the document revision, accepted job-set digest, graph root,
unresolved-demand digest, coverage digest, and operation contracts.

## Process topology

The scalable target topology is:

```text
parser projection process
    -> durable carrier manifest

typing worker processes
    -> durable typing graph manifests

closure workers on one or many machines
    -> immutable deltas admitted through PostgreSQL

finalisation worker
    -> bounded factor/residual revisions and graph manifest

fresh serializer process
    -> compact reference receipt only

publication transaction
    -> staged build row becomes committed

parity verifier
    -> compact manifest comparison before any row-level diff
```

A process exit is the strongest heap-release boundary. The operating system, not
Python allocator heuristics, guarantees reclamation of the complete address
space.

## Finalisation and receipt contract

Large families are sealed before owner release:

- factors;
- residuals;
- proposals;
- observation deltas;
- coverage notices;
- jobs and receipts;
- state deltas;
- boundary summaries.

Each family descriptor records count, byte count, ordered digest, storage kind,
and encoding. The heavy owner maps are cleared, garbage collection and
`malloc_trim` are attempted, and only then is a fresh interpreter launched.

The serializer receives paths and manifest references only. It never receives
the owner object or full factor population.

The outward receipt contains compact identities and family descriptors. Large
families remain behind durable references.

## Bounded publication

Publication consumes each verified family in small batches. No
`executemany` call receives the document-wide parameter population.

The publication protocol is:

```text
persist family batch
-> advance durable cursor
-> release batch
-> persist compact fixed-point/execution receipt
-> stage publication_build
-> commit publication_build
```

Atomicity comes from the final small state transition, not from constructing one
giant client-side payload.

## Manifest-first parity

Reference and resumed runs compare:

- document revision;
- graph root;
- fixed-point certificate;
- owner fingerprint;
- family counts, byte counts, and ordered digests;
- logical typing references;
- finalisation contract.

Row-level comparison is performed only when a compact manifest differs. Two full
receipts are never decoded solely to prove equality.

## Memory budgets

The global 8 GiB limit is a last safety net. Lower stage budgets are enforced:

| Stage | Soft | Hard |
|---|---:|---:|
| Parser projection | 3.0 GiB | 4.0 GiB |
| Typing | 4.0 GiB | 5.0 GiB |
| Closure | 5.0 GiB | 6.0 GiB |
| Finalisation | 4.0 GiB | 5.5 GiB |
| Serialization | 2.0 GiB | 3.0 GiB |
| PostgreSQL publication | 2.0 GiB | 3.0 GiB |
| Parity comparison | 1.5 GiB | 2.5 GiB |

Every semantic progress sample also records the applicable stage budget and
remaining headroom. A stage crosses its own hard boundary before exhausting the
whole process envelope.

## Disk retention

Disk has a separate budget and four retention classes:

- `authoritative_reusable`;
- `derived_reproducible`;
- `diagnostic`;
- `failed_attempt_temporary`.

The sole authoritative reusable copy is never automatically reclaimed. Derived
or diagnostic data becomes reclaimable only after a durable successor is
registered.

## Formal model

`formal/DistributedSemanticExecution.tla` specifies:

- blocked, ready, leased, completed, retryable, and failed jobs;
- lease epochs and expiry;
- stale-result rejection;
- owner-revision admission;
- dependency readiness;
- fixed-point soundness;
- eventual completion or terminal failure under fairness assumptions.

The principal invariants are:

- `LeaseFencingSafety`;
- `ExactlyOneSemanticAdmission`;
- `OwnerRevisionAgreement`;
- `CompletedDependencies`;
- `FixedPointSoundness`.

## Validation sequence

Before another complete exact-0008 reference run:

1. run the self-hosted focused regressions;
2. run `scripts/run_post_closure_probe.py` against the completed finalisation
   checkpoints;
3. require isolated serializer PSS below its 3 GiB hard budget;
4. apply migration 026 in the disposable acceptance database;
5. exercise bounded finalisation-to-publication persistence;
6. verify compact publication and manifest parity;
7. launch a reference run;
8. launch injected-stop/resume;
9. compare semantic and publication identities.

A run is not promotable merely because it eventually completes. Every stage must
be observable, bounded, restartable from durable references, and either complete
or fail with a finite diagnostic.
