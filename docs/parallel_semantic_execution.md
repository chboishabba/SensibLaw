# Parallel semantic execution

This tranche applies the existing one-document semantic authority to the two
measured exact-0008 bottlenecks: local typing and streaming closure. Execution
partitions remain physical fibres. They do not become semantic documents and
cannot publish independently.

## Serial baseline

The committed baseline is
[`docs/calibration/exact_0008_serial_baseline.v1.json`](calibration/exact_0008_serial_baseline.v1.json).
It records the failed one-worker trace:

- 1,375,469 canonical characters;
- four complete parser-fibre checkpoints;
- approximately 2 h 35 min in local typing;
- approximately 1 h 18 min in streaming closure;
- no completed document and no compiler publication.

The timing and large semantic counts are approximate observations from the
failed trace. Parser coverage and failure identity are derived from committed
checkpoint/state artifacts. The baseline has no final semantic or publication
identity because compilation did not reach either boundary.

Regenerate it from a saved trace with:

```bash
uv run python scripts/normalize_exact_0008_baseline.py \
  --state .tmp/exact-0008-current/trial-1/gwb/local_pnf_compilation_state.json \
  --parser-summary-root .tmp/exact-0008-current/trial-1/gwb/local_pnf_compilation_state_chunks \
  --output docs/calibration/exact_0008_serial_baseline.v1.json
```

## Local typing

The legacy atom/mention and mention/parser-observation joins scanned one entire
collection for every row in the other collection. Production now uses an
immutable token interval tree and reports query work. For `A` atoms, `M`
mentions and `K` real overlaps, the target is output-sensitive:

```text
O(A + M + K)
```

rather than `O(A × M)`. A left interval is owned by its start coordinate, but
its leaf interface is extended through the interval's real end so a match that
crosses a leaf boundary is not lost.

The local-typing stage is decomposed into named kernels:

- `atom_mention_matching`;
- `parser_observation_matching`;
- `structural_hypothesis_derivation`;
- `local_type_carrier_build`;
- `untyped_diagnostic_generation`;
- `diagnostic_summary`.

Each kernel records elapsed time, input/output counts, RSS, PSS and USS. Matching
kernels additionally record leaf work and actual match counts. Structural
hypotheses, local-type carriers and diagnostics are also divided into immutable
bounded leaves and checkpointed independently.

## Process-backed execution without parser duplication

The measured local-typing and closure kernels are Python CPU work. Thread pools
alone cannot guarantee use of more than one CPU core. Production therefore has
an opt-in bounded process pool for semantic leaves and pure solver jobs:

```text
SENSIBLAW_SEMANTIC_PROCESS_WORKERS=4
SENSIBLAW_TYPING_OVERLAP_PROCESS_WORKERS=4
SENSIBLAW_SEMANTIC_MP_CONTEXT=forkserver
```

Workers receive only bounded JSON-like typing leaves or immutable `SolverJob`
values. They do **not** receive or load:

- spaCy or the parser pipeline;
- the complete parsed document;
- the annotation graph;
- the full relational bundle;
- the complete semantic worktree.

The parent process remains the sole document semantic owner. It merges immutable
leaf outputs, admits solver receipts and performs deterministic reductions. The
process pool is destroyed before PostgreSQL persistence. The exact acceptance
receipt records worker PIDs and fails unless at least two distinct semantic
worker processes actually performed work.

## Mini, midi and mega typing graphs

Typing overlap, structural-hypothesis, local-carrier and diagnostic work is
assigned to bounded leaves. A leaf checkpoint contains:

- source, parser and typing-contract identity;
- exact owned carrier or ordered input identity;
- input and output digests;
- immutable semantic output records;
- boundary interface references where applicable;
- an exact-coverage and local-fixed-point certificate;
- elapsed and complexity receipts;
- the worker PID that produced it.

Missing leaves may execute concurrently. Completed leaves are immutable and
reused after a stopped run. Parent nodes store child graph references and
boundary interfaces only. Every hierarchy receipt must report:

```text
descendant_bytes_reconstructed = 0
flattening_free = true
```

The physical root graph reference may change with leaf capacity or arity. The
`logical_typing_ref` is derived from source/parser/typing identity and the
canonical output digest only, so worker count, completion order and partition
layout have no semantic effect.

## Typing checkpoint and resume

The durable path is:

```text
parser-fibre checkpoints
→ overlap leaf checkpoints
→ structural-hypothesis leaf checkpoints
→ local-type-carrier leaf checkpoints
→ diagnostic leaf checkpoints
→ typing hierarchy root receipts
```

A stopped run reuses every completed leaf whose source hash, parser contract,
typing contract, input identity and build key still match. The compiler does not
claim that arbitrary in-memory Python state is resumable.

## Closure

The bounded semantic owner and scheduler lease immutable jobs by semantic
`OwnerKey`, not by permanent text ownership. Pure operator solving can run in
the bounded semantic process pool; receipt admission and factor reduction remain
transactional in the one document owner. The execution surface adds:

- per-reduction-batch proposal and factor-scan accounting;
- settled-group rescan counts;
- changed-factor and revision counts;
- dependency fan-out;
- closure progress samples with RSS/PSS/USS;
- pure solver-receipt checkpoints keyed by `job_ref`;
- deterministic solver-receipt replay after interruption;
- worker-PID evidence for actual process parallelism.

The durable closure handoff is a replay contract, not a Python-object snapshot.
It binds the document, source, parser, build and contract identities and records
content-addressed references for immutable observation-delta batches, proposal
batches, solver receipts, reduction keys, owner revisions and the unresolved
frontier. A resumed process verifies those references, creates a fresh owner and
canonically replays them before leasing new work. Completed process-worker jobs
and their receipts are reused; reconstruction admissions are reported
separately from new admissions. Missing, corrupt or identity-incompatible
handoffs fail closed.

Important ratios are emitted in the amplification report:

```text
proposals_examined / proposals_emitted
factor_scans / changed_factors
```

## Semantic amplification

`semantic-amplification-report.json` explains large output families rather than
assuming they are inevitable. It records:

- meets by type;
- refinements by transition;
- no-op refinements;
- duplicate resulting factor revisions;
- demands by subject kind and source operation;
- duplicate and semantically equivalent demands;
- candidate-set size distribution;
- closure scan/change ratios.

This report is diagnostic. It does not delete or merge semantic rows. Any later
deduplication must first prove semantic parity.

## Checkpoint and execution controls

Set a durable semantic checkpoint directory and bounded work policy:

```text
SENSIBLAW_SEMANTIC_CHECKPOINT_DIR=/path/to/semantic-checkpoints
SENSIBLAW_TYPING_WORKERS=4
SENSIBLAW_TYPING_LEAF_CAPACITY=4096
SENSIBLAW_TYPING_HIERARCHY_ARITY=4
SENSIBLAW_TYPING_RELATION_LEAF_SIZE=4096
SENSIBLAW_TYPING_MENTION_LEAF_SIZE=4096
SENSIBLAW_SEMANTIC_PROCESS_WORKERS=4
SENSIBLAW_TYPING_OVERLAP_PROCESS_WORKERS=4
```

Failure injection is available for tests:

```text
SENSIBLAW_TYPING_STOP_AFTER_LEAVES=N
SENSIBLAW_TYPING_TAIL_STOP_AFTER_LEAVES=N
SENSIBLAW_CLOSURE_STOP_AFTER_ACTIVATION_COMPLETION=N
SENSIBLAW_CLOSURE_STOP_AFTER_OWNER_BATCH_ADMISSIONS=N
SENSIBLAW_CLOSURE_STOP_AFTER_RECEIPTS=N
SENSIBLAW_CLOSURE_STOP_AFTER_DIRTY_REDUCTIONS=N
```

These controls stop only after immutable outputs and a durable owner handoff
have been written. Resume must reuse completed activation leaves and solver
receipts, reconstruct the owner frontier and continue without semantically
duplicating admission.

## Exact-0008 acceptance

Reuse the failed trial output root so its parser state and four parser-fibre
checkpoints remain available. Keep one parser worker because parser concurrency
is not the measured bottleneck and the committed checkpoint/build identity was
created with one. Use four **process-backed semantic workers** for typing and
closure:

```bash
uv run python scripts/run_exact_0008_parallel_acceptance.py \
  --database-url postgresql://postgres@127.0.0.1:5433/sensiblaw_tranche \
  --input-path /path/to/0008.epub \
  --output-root .tmp/exact-0008-current/trial-1 \
  --acceptance-root .tmp/exact-0008-parallel-acceptance \
  --typing-workers 4 \
  --closure-workers 4 \
  --owner-partitions 8 \
  --parser-workers 1 \
  --worker-budget 4
```

The wrapper delegates compilation and SQL publication verification to the
strict acceptance runner. It compares local-typing and closure time with the
serial failed baseline, requires multiple observed semantic worker PIDs and
captures resource, overlap, frontier, latency and amplification receipts. A
failed historical baseline cannot prove final semantic parity. First establish
a successful rolled-back semantic reference, then run a separate injected-stop
checkpoint and compare the resumed run with that reference:

```bash
# Successful semantic reference.
uv run python scripts/run_exact_0008_parallel_acceptance.py \
  --database-url postgresql://postgres@127.0.0.1:5433/sensiblaw_tranche \
  --input-path /path/to/0008.epub \
  --output-root .tmp/exact-0008-current/trial-1 \
  --acceptance-root .tmp/exact-0008-streamed-acceptance/reference \
  --typing-workers 4 --closure-workers 4 --owner-partitions 8 \
  --parser-workers 1 --worker-budget 4

# Forced stop after a durable receipt, followed automatically by resume.
uv run python scripts/run_exact_0008_parallel_acceptance.py \
  --database-url postgresql://postgres@127.0.0.1:5433/sensiblaw_tranche \
  --input-path /path/to/0008.epub \
  --output-root .tmp/exact-0008-current/trial-1 \
  --acceptance-root .tmp/exact-0008-streamed-acceptance/resumed \
  --reference-semantic-receipt \
    .tmp/exact-0008-streamed-acceptance/reference/semantic-checkpoints/semantic-execution-receipt.json \
  --reference-acceptance-report \
    .tmp/exact-0008-streamed-acceptance/reference/parallel-acceptance-comparison.json \
  --inject-stop-boundary receipt --inject-stop-after 1 \
  --typing-workers 4 --closure-workers 4 --owner-partitions 8 \
  --parser-workers 1 --worker-budget 4
```

The default 6/8 GiB limits in this runner are provisional machine-safety bounds,
not optimisation acceptance thresholds. The report must still expose retained
state, peak RSS/PSS/USS and work amplification.

Production artifact handoff consumes the compiler-owned carrier after its
serialized families have been built. Reference-binding transforms reuse
unchanged immutable factors, revision normalization hashes only factors named
by demands, and large graph identities use incremental canonical hashing.
Bounded closure proposal batches (at most 65,536 rows) use the faster native
JSON encoder for replay-integrity hashes; carriers above 131,072 direct rows
stay on the incremental path. The materialised compatibility policy remains
non-consuming. This keeps the same artifact descriptors and digests without
retaining compiler-native graphs, several copied graph revisions and a whole
encoded graph at once, while avoiding Python-level chunk encoding for bounded
replay batches.

`rss.jsonl` is run-scoped evidence and is truncated when a strict acceptance
attempt starts. Reusing an acceptance directory therefore cannot import a
failed attempt's peak into the current trace or its resource audit.

## Acceptance invariants

A tranche result is acceptable only when:

1. exact parser owner coverage remains complete;
2. canonical and partitioned fixture outputs agree;
3. valid leaf capacities have the same logical typing identity;
4. completed leaves and solver receipts are reused after injected stops;
5. hierarchy nodes reconstruct zero descendant bytes;
6. at least two distinct semantic worker PIDs performed work;
7. closure reaches the same document fixed point;
8. manifest digests and SQL publication verification succeed;
9. exactly one completed build and compiled occurrence are visible;
10. no physical partition field enters semantic parity.
11. activation and owner execution overlap while buffering remains bounded;
12. owner admission is ordered, reductions remain single-owner and settled
    keys are not materially rescanned;
13. the resumed run reports reconstruction, reuses worker outputs and receipts,
    and matches the successful reference's semantic, manifest and persistence
    identities;
14. both acceptance runs roll back to their calibrated pre-run row counts.
