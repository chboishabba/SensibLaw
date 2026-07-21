# Streaming Semantic Fixed-Point Implementation Status

This document complements `StreamingSemanticFixedPoint.md` with the concrete implementation
map and the distinction between active production paths and available extension contracts.

## Active catalogue path

The catalogue compiler currently executes:

```text
parallel document processes
→ whole-document spaCy parse per process
→ immutable complete sentence observation deltas
→ bounded keyed owner admission
→ revision-bound operator closure jobs
→ immediate proposal admission and reduction
→ adjacency-indexed constraint worklist
→ deterministic streamed-reduction projection into refined PNF
→ local and regional fixed-point certificates
→ Legal IR projection
→ transactional PostgreSQL persistence
```

The parser and semantic stages overlap across documents. Inside one document, semantic
sentence jobs stream to and from the logical owner continuously after the parser record is
available. The compiler does not yet ask spaCy to stream an unfinished document model.

## Intra-document parser parallelism

`parser_delta_executor.py` provides two explicit contracts.

### WholeDocumentSentenceParserExecutor

This is the conservative default. It parses one canonical document and projects complete
sentence batches. It is safe for every current source because spaCy retains full-document
context.

### PresegmentedRegionParserExecutor

This permits multiple parser processes for one document only when a trusted region map has
already fixed:

```text
document identity
region identity and order
character interval
token interval and expected count
coverage barrier
```

The executor restores global coordinates after regional parsing and rejects any region whose
parsed token count disagrees with the supplied map. Physical completion order has no effect
on delta or graph identity.

This executor is appropriate for structurally segmented legislation, judgments, and hearing
transcripts once the ingestion layer supplies authoritative sections or paragraph regions.
It must not infer arbitrary chunks merely to create parallel work.

## Continuous owner execution

`streaming_execution.py` interleaves:

```text
offer parser delta
→ accept or defer under semantic pressure
→ execute ready closure jobs
→ admit each returned receipt
→ reduce its affected group immediately
→ release deferred parser deltas
→ repeat
```

It reports separate elapsed totals for observation admission, pure closure execution, and
owner-side proposal reduction. Closure time is the sum of worker execution time; owner time
is the sequencer/reducer cost.

## Convergent state and explicit retraction

The normal ledger is append-only and ACI. Corrections are not destructive updates. They are
represented by:

```text
SupersessionNotice
RetractionNotice
StaleReceiptRecord
replacement SolverJob
```

A stale result is never admitted merely because it completed. If all referenced inputs remain
active, a receipt from an older document revision remains valid. If an input has been
superseded, the receipt is retained as stale execution evidence, its proposals are not
admitted, and only the affected job is rescheduled against replacement refs.

Previously admitted proposals whose input is superseded remain in the historical ledger but
are excluded from the active materialised view through an explicit retraction notice. This
preserves replayability without last-writer-wins state.

## Semantic backpressure

`BackpressurePolicy` bounds:

```text
pending jobs
in-flight jobs
dirty reduction groups
estimated branching mass
deferred parser deltas
```

When pressure is high, parser deltas are deferred without being discarded. If the bounded
inbox is full, the runtime raises `BackpressureCapacityError`; the caller must pause and retry.
The active stream runner drains closure work and reductions before releasing deferred deltas.

Backpressure events are persisted so throughput decisions can be reviewed against the actual
semantic frontier rather than only CPU utilisation.

## Constraint worklist

`constraint_worklist.py` indexes each constraint by incident factors. Initial compilation
processes every declared constraint. Incremental calls process only constraints adjacent to
changed factors. A changed factor with no incident constraint performs zero constraint work;
it does not fall back to a full graph scan.

The result records work items, assessments, propagation waves, changed factors, and an empty
pending frontier at the fixed point.

## Regional coordination

`HierarchicalDocumentCoordinator` registers region summaries and regional certificates,
routes cross-region boundary obligations, and blocks the document fixed point until all local
regions are stable and every routed local boundary obligation is discharged.

Regional summaries contain stable factors, unresolved external refs, possible cross-scope
hosts, definition-scope obligations, and coverage evidence. External residuals may remain;
runnable local boundary work may not.

## Streamed reduction as PNF source of truth

`streaming_reduction_projection.py` converts reduced streamed proposals into compatibility
`Factor` values without reparsing or re-running operator composition. It preserves:

```text
all proposal alternatives
proposal and declaration refs
source and observation provenance
qualifier and role coordinates
reduction residuals
factor revision identity
```

The resulting graph is the input to constraint propagation and Legal IR. The previous batch
operator bridge remains a compatibility utility for older artifacts, not the source of truth
for new catalogue builds.

## Stage timing

The active compiler records:

```text
canonical_normalization
parser_annotation               backend=spacy
coordinate_validation
mention_licensing
parser_observation_projection
base_proposal_generation
base_proposal_reduction
composition_generation          owner admission/backpressure
closure_executor_evaluation     pure worker cost
composition_proposal_reduction  owner materialisation cost
constraint_fixed_point
postgres_persistence
```

The Legal IR probe separately records streamed compilation, Legal IR projection, legacy
witness extraction, comparison, and semantic-build export.

## Stage cache and invalidation

Stage keys are derived independently for parser, observation projection, base proposals,
base reduction, composition declarations, composition reduction, constraint fixed point,
and Legal IR projection.

`cached_parser.py` and the memory/PostgreSQL stage cache implement actual parser-stage reuse.
A repeated parser key returns the immutable prior parser output and a reuse receipt without
calling the parser again. Contract or canonical-text changes produce a new key. Changes to
Legal IR projection do not invalidate the parser key.

The database stores immutable stage outputs and reuse receipts. Reuse is an execution fact,
not semantic promotion. Whole-document publication remains the final immutable build boundary.

## PostgreSQL migrations

The implementation adds:

```text
018_streaming_semantic_fixed_point.sql
019_streaming_semantic_coordination.sql
020_semantic_stage_build_cache.sql
```

These persist the convergent ledger, jobs, receipts, reductions, state deltas, coverage,
fixed-point certificates, timings, supersession/retraction records, stale receipts,
backpressure, constraint work, regional coordination, stage outputs, and reuse receipts.

Database constraints prohibit execution-driven identity promotion, legal-truth closure,
shared mutable graph publication, and admission of stale receipt proposals.

## Optional Zelph executor

Zelph implements the same pure `ClosureExecutor` boundary as Python. The concrete benchmark
covers modality/polarity, condition, exception, and transition candidates. It reports
serialisation, engine, and decoding costs separately and requires exact proposal and reduction
digests.

An unavailable Zelph executable is reported as unavailable and never treated as parity.
Parity is necessary but insufficient for adoption: the end-to-end document closure phase must
also improve.

## Validation

`streaming-semantic-fixed-point.yml` applies PostgreSQL migrations, runs Ruff, executes the
fixed-point, coordination, backpressure, worklist, cache, parser executor, timing, and Zelph
boundary tests, runs the optional parity command, performs an offline catalogue build, and
verifies durable fixed-point and timing evidence.

## Authority boundary

None of the following establishes legal truth:

```text
parallel parser completion
ledger convergence
proposal reduction
constraint assessment
fixed-point certification
database persistence
stage reuse
Python closure
Zelph closure
```

Identity, applicability, breach, liability, and professional legal assessment remain explicit
external or review-bearing layers.
