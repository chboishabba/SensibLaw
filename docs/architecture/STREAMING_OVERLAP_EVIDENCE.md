# Streaming overlap evidence

Status: normative measurement companion to `STREAMING_SEMANTIC_PACMAN.md`.

This document corrects an important interpretation error exposed by the first
fresh overlapped Gate-A run.  A high fraction of semantic work complete at
parser EOF is **not** sufficient evidence of useful parser/semantic overlap.

## Why raw EOF completion can be misleading

For ordered parser partitions with semantic sentence counts

```text
p1, p2, ..., pn
```

a completely serial partition pipeline can finish all semantic work from
`p1..p(n-1)` before parser EOF on the final partition `pn`.

Therefore the serial EOF floor is:

```text
serial_eof_floor = sum(p1..p(n-1)) / sum(p1..pn)
```

Only semantic completion above that floor is evidence attributable to overlap:

```text
overlap_gain = max(0, semantic_complete_at_eof - sum(p1..p(n-1)))
```

The Python owner is:

- `src/runtime/streaming_overlap_evidence.py`

The corresponding Agda receipt owner is:

- `DASHI/Cognition/PNF/StreamingPhysicalOverlapReceiptExact.agda`

## First fresh receipt and the correction

The first identical fresh streaming Gate-A workload reported structural
partition sentence counts:

```text
168, 73, 5, 1
```

and:

```text
semantic_sentences_at_parser_eof = 246 / 247
parser_semantic_overlap_ns        = 6,225 ns
```

The raw EOF completion was therefore about 99.6%, but:

```text
pre-final structural work = 168 + 73 + 5 = 246
serial EOF floor          = 246 / 247
observed EOF completion   = 246 / 247
overlap completion gain   = 0 / 247
```

So that run proved bounded/correct streaming execution but **did not prove
material coarse-grained overlap**.  The raw 99.6% number is entirely explained
by physical partition geometry.

Do not cite `stream_completion_fraction` alone as Pac-Man performance evidence.
Always report at least:

```text
partition_sentence_counts
serial_eof_floor_fraction
observed_eof_completion_fraction
overlap_completion_gain_sentences
overlap_completion_gain_fraction
parser_semantic_overlap_ns
post_parser_tail_ns
```

## Highest-alpha probe before repartitioning

The same run also exposed a more direct physical hypothesis. Gate-A leased four
partitions and called spaCy with `pipeline.pipe(batch_size=4)`.  spaCy may finish
most or all of that physical batch before yielding the first completed `Doc`,
which can collapse observable overlap even though the consumer queue is correct.

The streaming runtime therefore permits a controlled parser-pipe batch override
without changing the leased partition batch:

```text
lease batch = 4
pipe batch  = 1
queue bound = 1
```

Run the canonical benchmark with:

```bash
python scripts/run_direct_gate_a_benchmark.py \
  --database-url "$DATABASE_URL" \
  --text-file README.md \
  --parser-contract-ref parser-document-fibres:v0_2 \
  --batch-size 4 \
  --pipe-batch-size 1
```

`--pipe-batch-size` is a physical streaming probe only.  It does not change
partition ownership, stable evidence identity, PNF semantics, or the production
authority cut.

The benchmark runner now also accepts `--target-chars` and `--context-chars` so
partition granularity can be tested *after* the pipe-yield hypothesis.

Recommended experiment order:

```text
A. existing structural partitions, lease=4, pipe=4
B. same partitions, lease=4, pipe=1
C. only if B still has negligible overlap: finer target_chars with pipe=1
D. only if partition-fused overlap remains weak: expose an earlier stable parser
   prefix/event carrier
```

This order avoids multiplying context overlap or changing the parser partition
contract before testing the simpler batching explanation.

## Formal interpretation

`StreamingSemanticPacmanKernelExact.agda` still owns the semantic theorem:

```text
state(prefix ++ suffix) = continue(state(prefix), suffix)
```

`StreamingPhysicalOverlapReceiptExact.agda` now separately records physical
partition accounting:

```text
preFinal + finalPartition = total
preFinal + overlapGain    = completeAtParserEOF
```

If `overlapGain = 0`, then a high raw EOF completion percentage is not evidence
of useful concurrency.

No benchmark threshold changes semantic correctness or production authority.
Bounded G3 direct/reference parity remains the production cutover gate.
