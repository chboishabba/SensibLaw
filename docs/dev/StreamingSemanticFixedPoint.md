# Streaming Semantic Fixed-Point Compiler

## Status

This document defines the execution contract for the document-local semantic compiler.
It does not define legal truth, applicability, identity resolution, breach, liability, or
professional review outcomes. Execution produces candidate semantic evidence only.

## Architectural change

The compiler is no longer modelled as:

```text
parse the whole document
→ construct one large candidate graph
→ reduce late
→ project Legal IR
```

Its execution algebra is:

```text
canonical source
→ parser observation deltas
→ coordinate admission and exact deduplication
→ base immutable proposals
→ indexed base reduction
→ declaration activation worklist
→ revision-bound closure jobs
→ derived proposal deltas
→ indexed compositional reduction
→ affected constraint propagation
→ document-local fixed-point certificate
→ Legal IR projection
→ immutable semantic build
```

The important boundary is not “one worker per document”. It is:

> One reducible semantic coordinate has one logical admission authority, while any
> number of parser and solver workers may concurrently produce immutable deltas for it.

The owner is a streaming sequencer and reducer, not the only compute worker.

## Compiler state

For document `d`, the runtime state is:

```text
S_d = (O_d, P_d, R_d, U_d, C_d, W_d, J_d, B_d)
```

where:

- `O_d` is the append-only parser/source observation ledger;
- `P_d` is the append-only factor-proposal ledger;
- `R_d` is the deterministic reduced materialised view;
- `U_d` is the residual and incompatibility ledger;
- `C_d` is coverage and completion evidence;
- `W_d` is the dirty reduction/rule/constraint worklist;
- `J_d` is the set of pending and in-flight revision-bound jobs;
- `B_d` is the set of unresolved local boundary obligations.

Workers principally grow `O_d`, `P_d`, and `U_d`. They never overwrite `R_d`.
The owner derives `R_d` deterministically from the convergent ledger.

## Convergent ledger

The observation, proposal, receipt, coverage, derivation, incompatibility, and residual
carriers are immutable and content-addressed. Their merge operation is set union over
stable references and is required to be:

```text
associative
commutative
idempotent
```

Consequently duplicate worker delivery is harmless, physical arrival order does not
change the ledger identity, and compatible replicas can converge without last-writer-wins
semantics.

This CRDT-like property applies to the ledger. The refined graph remains a deterministic
materialised view over that ledger; it is not itself collaboratively mutated.

## Keyed ownership

The implemented owner key is:

```text
(document_ref, scope_ref, factor_family)
```

Examples:

```text
(document D, section 4, semantic.eventuality)
(document D, section 4, semantic.normative_relation)
(document D, section 7, semantic.legal_transition)
(document D, document-global, semantic.definition_scope)
```

Owner keys are deterministically mapped onto physical partitions. Physical owners may be
actors, event-log partitions, optimistic database transactions, or replicated state
machines. The semantic requirement is either one canonical admission order per owner key
or an order-independent merge.

## Bidirectional streaming

Owners continuously expose three logical streams.

### Work stream

```text
observation delta admitted
coverage region closed
reduction group became dirty
declaration prerequisites became available
constraint neighbourhood changed
```

Each work item is content-addressed and revision-bound.

### State-delta stream

```text
observation admitted
proposal admitted
factor revision changed
alternative retained
residual introduced
residual discharged
```

These records permit durable replay and explain why a graph revision changed.

### Completion stream

```text
sentence parser-complete
section reduction-stable
rule frontier empty
N jobs remain in flight
regional boundary summary emitted
local fixed point reached
```

Idle workers do not imply completion. Pending jobs, dirty groups, open barriers, and local
boundary obligations are part of the completion state.

## Parser and solver topology

The operational topology has three independently tunable pool sizes:

```text
n parser/document processes
m active keyed owner partitions
q pure closure executors
```

The current corpus runner uses process-level document parsing and persistence. Within one
document, complete parser sentences are projected into immutable deltas and independent
operator-composition jobs may execute concurrently. The owner alone admits their receipts.

A future parser adapter may emit sentence or bounded sentence-batch deltas directly while
spaCy is running. That adapter must preserve pre-established canonical character, token,
sentence, and document coordinates; chunk boundaries must not silently change identities.

## Delta granularity

A delta is not one token and is not necessarily a whole document. The initial semantic
unit is a complete parser sentence. Each delta records:

```text
document_ref
batch_ref
scope_ref
sequence_no
parser contract
canonical token interval
canonical character interval
observation refs
coverage barrier
coverage-complete flag
```

Larger rules may require section or document coverage even when their positive inputs were
observed earlier.

## Revision-bound speculative jobs

A job records:

```text
owner key
declaration ref
input document revision
exact immutable input refs
input payload slice
rule-set revision
coverage requirements
assumptions
priority
```

A receipt records the same contract plus output proposal refs, residuals, backend identity,
and execution metrics.

Advancing the document from revision `v` to `v+k` does not by itself invalidate a receipt
computed at `v`. The owner admits the receipt when its referenced inputs and rule-set
revision remain valid. If an input is superseded, only the affected job is rescheduled. If
new relevant input appears, the prior positive result remains and a delta job computes the
missing consequences.

This is convergent eventual consistency, not arbitrary eventual consistency.

## Monotone output and finalising claims

The following positive evidence may stream before a region closes:

```text
candidate
evidence
derivation
incompatibility
residual
```

The following are finalising claims and require explicit coverage barriers:

```text
absence
unique
exhausted
closed
all alternatives enumerated
```

For example, a worker may emit `candidate attachment H1 found` while parsing continues. It
may not emit `H1 is the only attachment` until the declared scope is parser-complete and
all applicable jobs and reductions have been discharged.

## Staged reductions

### Coordinate admission

Canonical spans and token ranges are validated before semantic work. Malformed candidates
become explicit diagnostics rather than late document failures.

### Base proposal reduction

Atomic parser-derived proposals are grouped by stable coordinates. Exact duplicates are
collapsed, compatible provenance is aggregated, impossible combinations are excluded, and
incompatible occupied coordinates remain alternatives with residuals.

### Declaration-driven closure

Only declarations whose required input families changed and whose coverage barrier is
satisfied are activated. Jobs receive immutable input slices rather than mutable graph
objects.

### Compositional reduction

Each returned closure delta is reduced immediately. The compiler does not permit a large
derived frontier to accumulate before reduction.

### Constraint propagation

Changed factors enqueue only incident constraints and dependent attachments. The intended
steady-state implementation is an adjacency-indexed worklist, not repeated full-graph
scanning.

## Regional decomposition

Large judgments and transcripts may use hierarchical ownership:

```text
document coordinator
  ├─ sentence/section owner A
  ├─ sentence/section owner B
  ├─ sentence/section owner C
  └─ document-global owner
```

A region exports a boundary summary containing:

```text
stable local factor refs
unresolved external refs
possible cross-scope hosts
definition-scope obligations
coverage notice refs
```

The document coordinator solves only the boundary graph. Regional fixed points are useful
before the whole document closes, but do not certify document completeness.

## Fixed-point certificate

A document-local fixed point is reached only when:

```text
unconsumed observation deltas = 0
dirty reduction groups = 0
pending jobs = 0
in-flight jobs = 0
unresolved local boundary obligations = 0
open required coverage barriers = 0
resource limit reached = false
```

External residuals may remain. They are evidence that local execution is sound but cannot
resolve an external question. The certificate always preserves:

```text
identity_promoted: false
legal_truth_closed: false
```

Legal IR projection may consume only a stable document-local revision and its certificate.

## PostgreSQL evidence

Migration `018_streaming_semantic_fixed_point.sql` persists:

```text
semantic_observation_delta
semantic_coverage_notice
semantic_solver_job
semantic_solver_receipt
semantic_state_delta
semantic_materialized_reduction
semantic_region_boundary_summary
semantic_fixed_point_certificate
semantic_stage_timing
```

Database checks prohibit last-writer-wins graph publication, shared graph mutation,
identity promotion, and legal-truth closure by the execution lane.

## Timing and optimisation metrics

Per-document timing records distinguish:

```text
canonical_normalization
parser_annotation              backend=spacy
coordinate_validation
mention_licensing
parser_observation_projection
base_proposal_generation
base_proposal_reduction
closure_executor_evaluation
composition_proposal_reduction
constraint_fixed_point
legal_ir_projection
postgres_persistence
```

Reduction stages report input/output nodes and edges, proposals generated, duplicate
collapse, invalid rejection, retained alternatives, residual emission, tokens processed,
throughput, reduction ratio, and edges removed per second.

The goal is not maximum raw worker count. The goal is to remove safe branching mass early
without erasing ambiguity or provenance.

## Backpressure

Parser admission must be bounded when semantic work accumulates. Recommended pressure
signals are:

```text
queued observation bytes
pending dirty groups
in-flight closure jobs
estimated branching mass
resident document-state bytes
```

When a document exceeds a high-water mark, its parser stream pauses while other documents
continue. This prevents streaming from recreating the former large-candidate-graph
failure mode in a queue.

## Zelph boundary

Zelph is an optional `ClosureExecutor`. It receives one immutable job and returns candidate
proposals plus a derivation receipt. It does not own state and cannot:

```text
admit observations
merge compatibility groups
select one ambiguous alternative
finalise absence
close identity
promote a legal conclusion
```

The parity harness measures fact serialisation, engine execution, result decoding, derived
proposal count, canonical proposal identities, and deterministic reduction identities.
Zelph is adopted for a rule family only when total end-to-end time improves and the Python
and Zelph candidate/reduction digests agree.

## Invalidation

Whole-document build keys remain the publication boundary. The streaming carriers expose
stable identities required for finer future invalidation:

```text
parser delta key
base proposal key
base reduction key
declaration/rule-set key
composition receipt key
materialised reduction key
Legal IR projection key
```

A later stage-key cache may therefore change Legal IR projection without reparsing, or
change one declaration without invalidating unrelated atomic proposal families.

## Non-goals and authority boundaries

Neither process parallelism, ledger convergence, database persistence, Python closure, nor
Zelph inference proves:

```text
cross-document identity
legal applicability
breach
liability
professional correctness
legal truth
```

Those remain explicit external or review-bearing layers.
