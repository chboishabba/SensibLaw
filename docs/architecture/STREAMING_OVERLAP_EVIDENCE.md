# Streaming overlap evidence

Status: normative measurement companion to `STREAMING_SEMANTIC_PACMAN.md`.

A high fraction of semantic work complete at parser EOF is **not** sufficient
evidence of useful parser/semantic overlap.  Physical partition geometry and
parser batching must be accounted for separately from semantic correctness.

## Formal owners

Before changing this experiment inspect:

- `DASHI/Cognition/PNF/StreamingSemanticPacmanKernelExact.agda`
- `DASHI/Cognition/PNF/StreamingPhysicalOverlapReceiptExact.agda`
- `DASHI/Cognition/PNF/StreamingPhysicalPartitionRefinementExact.agda`

The semantic prefix/suffix theorem is unchanged by every experiment on this
page.  Partition shape is physical scheduling only.

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

The Python owner is `src/runtime/streaming_overlap_evidence.py`.

## Experiment A: coarse partitions, pipe batch 4

The first fresh overlapped Gate-A workload reported partition sentence counts:

```text
168, 73, 5, 1
```

and approximately:

```text
semantic_sentences_at_parser_eof = 246 / 247
parser_semantic_overlap_ns        = 6,225 ns
```

The raw EOF completion was about 99.6%, but the serial floor was also 246/247.
Therefore:

```text
overlap completion gain = 0 / 247
```

This proved bounded/correct streaming execution but not material concurrency.

## Experiment B: same partitions, pipe batch 1

Experiment B kept the same physical partition ownership and changed only the
spaCy `pipeline.pipe` batch:

```text
lease batch = 4
pipe batch  = 1
queue bound = 1
```

Result on the identical fresh workload:

```text
parser/semantic active overlap  ~= 1.938 s
post-parser tail                ~= 6.240 s
direct total                    ~= 27.159 s
spaCy active work               ~= 4.036 s
overlap completion gain          = 0 sentences
```

Interpretation:

1. the producer/consumer implementation genuinely overlaps execution;
2. reducing the spaCy pipe batch materially increases active overlap;
3. the extra parser cost offsets that overlap, so end-to-end wall time is a wash;
4. semantic completion at EOF remains exactly the serial partition floor.

Therefore Experiment B is closed.  Do not keep tuning `pipe_batch_size` as if
active overlap alone were the objective.

## Experiment C: admissible physical partition refinement

The next experiment changes only physical partition granularity while keeping:

- exact disjoint owned source coverage;
- evidence-only bilateral context;
- ordered parser observations;
- the same packed-fibre/numeric PNF semantic authority;
- stable source-evidence identity;
- bounded queueing and zero prefix replay.

This is exactly the gate formalized by
`StreamingPhysicalPartitionRefinementExact.agda`.

The benchmark runner supports an approximate target partition count:

```bash
python scripts/run_direct_gate_a_benchmark.py \
  --database-url "$DATABASE_URL" \
  --text-file README.md \
  --parser-contract-ref parser-document-fibres:v0_2 \
  --batch-size 4 \
  --pipe-batch-size 1 \
  --target-partitions 12
```

`--target-partitions` derives a physical `target_chars` from source length;
structural boundaries still determine the actual cuts.  It is benchmark-only
and does not change production defaults.

Before paying for a database/parser run, compare physical plans with:

```bash
python scripts/plan_streaming_partition_refinement.py \
  --text-file README.md \
  --target-partitions 8 \
  --target-partitions 12 \
  --target-partitions 16
```

The planner reports owner sizes, skew, context duplication, and actual structural
partition count without invoking spaCy or PostgreSQL.

For the current 65,536-character Gate-A source, the existing boundary rule gives
roughly:

```text
requested ~8   ->  9 actual partitions, owner skew ~4.58x
requested ~12  -> 13 actual partitions, owner skew ~1.62x
requested ~16  -> 17 actual partitions, owner skew ~1.36x
```

At the current 2,048-character bilateral context, physical context work grows
substantially as partitions get finer.  The ~12 target is therefore the first
high-alpha C probe: it removes most owner skew without immediately taking the
largest context-duplication penalty.

The benchmark now reports:

```text
structural_partition_geometry
physical_parser_context_chars
physical_parser_context_work_ratio
```

alongside:

```text
partition_sentence_counts
serial_eof_floor_fraction
observed_eof_completion_fraction
overlap_completion_gain_sentences
overlap_completion_gain_fraction
parser_semantic_overlap_ns
post_parser_tail_ns
```

A refined schedule is useful only if its overlap/tail benefit exceeds its extra
parser/context cost.  More partitions are not intrinsically better.

## What follows Experiment C

Use this decision rule:

```text
C produces material overlap gain and/or lower wall time
    -> keep the best physical schedule and continue toward finer stable events

C produces more parser work but no semantic lead
    -> stop partition tuning; expose an earlier stable parser prefix/event carrier

C changes consumer-visible semantics
    -> reject the refinement and repair the physical carrier/parity boundary
```

Do not move directly from a failed C probe into hierarchy micro-optimization.
The purpose of C is to determine whether completed-partition granularity is
sufficient to realize the Pac-Man architecture at all.

## Formal interpretation

`StreamingSemanticPacmanKernelExact.agda` owns:

```text
state(prefix ++ suffix) = continue(state(prefix), suffix)
```

`StreamingPhysicalOverlapReceiptExact.agda` owns:

```text
preFinal + finalPartition = total
preFinal + overlapGain    = completeAtParserEOF
```

`StreamingPhysicalPartitionRefinementExact.agda` requires a finer physical
schedule to preserve exact/disjoint ownership, evidence-only context, ordered
observations, and final semantic authority.  Its performance receipt includes
parser work, semantic work, overlap, duplicated context, post-parser tail, and
end-to-end work.

No benchmark threshold changes semantic correctness or production authority.
Bounded G3 direct/reference parity remains the production cutover gate.
