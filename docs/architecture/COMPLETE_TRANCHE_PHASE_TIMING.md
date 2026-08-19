# Complete-tranche phase timing

The 12k numeric fixture is a kernel benchmark. It cannot identify the dominant
minutes/hours phase of a complete source-to-checkpoint ingest.

`scripts/benchmark_complete_tranche_phases.py` executes the existing tranche
runner in-process and interposes on two observational surfaces:

1. `PhaseReceipt` construction for exact completed outer-phase wall intervals;
2. `PhaseRecorder` emission for failure-surviving detailed progress while an
   outer phase is still running.

Neither surface changes semantic execution or receipt identity.

## Outer phase timing

A `PhaseReceipt` is constructed immediately after its phase work, so consecutive
receipt completions delimit the wall interval spent reaching each phase. This is
stronger than polling `tranche_run_state.json`: even two very fast phases
completed between filesystem polls are observed separately. Checkpoint reloads
are explicitly suppressed, so already-completed work on a resumed run is not
charged as new phase execution.

The observer writes `complete_tranche_phase_timings.json` after every newly
completed phase using fsync + atomic replace + parent-directory fsync. A failed
or interrupted tranche therefore retains timings for all receipts constructed
before the failure.

The timing report records, where the phase receipt exposes them:

- start/end epoch nanoseconds;
- monotonic wall nanoseconds/seconds;
- input/output token counts;
- new/reused semantic work units;
- the original phase detail payload.

Unavailable work/token fields remain `null`; they are not inferred from wall
subtraction.

## Detailed progress inside a long local-PNF phase

Outer receipts are deliberately not enough for a multi-hour numeric compile: a
terminal failure can occur before the local-PNF `PhaseReceipt` exists. The timed
entrypoint therefore replaces only the recorder implementation with
`DurablePhaseRecorder`.

Every stage transition, observation and 30-second heartbeat is appended exactly
once to the fsynced journal:

```text
<output-root>/<tranche>/local_pnf_compile_progress.jsonl
```

The append-only journal is the failure-surviving authority during execution. It
keeps per-heartbeat durability O(1) in the amount of prior progress history. If
compilation completes normally, the runner additionally writes the ordinary
aggregate recorder snapshot:

```text
<output-root>/<tranche>/local_pnf_compile_progress.json
```

The JSONL file exists and advances *before* the compiler returns. A later
PostgreSQL error therefore cannot erase the last active kernel or the progress
snapshots already observed.

The strict numeric compiler wires its active document handle into
`run_streaming_spacy_execution(progress_observer=...)` and samples compact
PostgreSQL execution state every 30 seconds. The snapshots include:

- parser partitions: total / ready / leased / completed / failed;
- completed parser token count and summed parser-active work;
- numeric-PNF work-item counts by operation/state;
- region closure progress by region kind;
- sparse-frontier reduction receipts grouped by region kind;
- sparse-frontier stage receipts already completed.

Named coordinator/publication boundaries are also emitted with monotonic elapsed
time:

- `sentence_closure_coordinator`;
- `sentence_adjacency`;
- `numeric_hierarchy`;
- `paragraph_adjacency`;
- `root_lookup_publication`;
- `numeric_execution_summary`;
- `numeric_authority_extraction`;
- `operational_build_publication`;
- `semantic_receipt_publication`;
- controlled-reuse measurement when explicitly enabled.

The numeric-PNF inner stage remains active through operational-build and semantic
receipt publication. It advances the document completion counter only after
those publication boundaries have succeeded. A receipt-FK failure is therefore
recorded as a failed `semantic_receipt_publication` kernel rather than as an
apparently completed numeric phase followed by an unexplained error.

## Reuse existing lower-level timing authority

Do not create a parallel timing table where the execution substrate already owns
one:

- completed parser partitions already persist `elapsed_ns` and token counts;
- sparse-frontier reductions already persist one `elapsed_ms` receipt per
  reduced interface;
- sparse-frontier document stages already persist `row_count` and `elapsed_ms`.

`src/runtime/numeric_kernel_progress.py` reads those compact receipt/queue tables
instead of rescanning document-sized semantic interiors.

Two timing bases must not be confused:

- summed parser-partition `elapsed_ns` is parser-active **work**;
- summed per-interface frontier `elapsed_ms` is reducer **work** by region kind.

Neither is automatically a disjoint wall interval. In particular, never add
summed interface work to coordinator wall time and call the result total elapsed
wall. The explicit monotonic coordinator intervals and outer phase wall remain
the wall-time authority.

A one-shot state report is available during or after a failed run:

```text
python scripts/report_numeric_kernel_progress.py \
  --database-url postgresql://... \
  --run-ref 'strict:document:...' \
  --document-ref 'document:...' \
  --progress-ledger /path/to/local_pnf_compile_progress.jsonl
```

The reporter also accepts the final `.json` aggregate when it exists. It
combines the current PostgreSQL snapshot with the last durable Python progress
event. This makes the diagnostic question precise:

```text
what kernel is active or failed?
what bounded work has completed?
which queue/fibre class remains?
where did completed reducer/parser work accumulate?
```

## Optimization ranking

The outer timing report feeds the same absolute-wall optimization policy used by
`src/runtime/performance_attention.py`. Hours outrank minutes, minutes outrank
seconds, and a long phase that should not exist in production remains high
priority until it is actually removed or bypassed.

Example complete run:

```text
python scripts/benchmark_complete_tranche_phases.py \
  --tranche GWB \
  --output-root /path/to/output \
  --database-url postgresql://...
```

Arguments not owned by the timing wrapper are passed through to
`run_complete_tranche.py`. The wrapper injects `--strict-exact`; use
`--compatibility-replay` only when intentionally benchmarking the historical
compatibility path.

For a genuinely fresh full-ingest measurement, use a fresh output root and a
clean run-derived database state. On a resumed run, checkpoint-loaded
`PhaseReceipt` objects are not charged as newly executed phases.

All of this is execution observability only. Timing and progress values never
participate in phase receipt identity or semantic authority.
