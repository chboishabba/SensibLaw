# Complete-tranche phase timing

The 12k numeric fixture is a kernel benchmark. It cannot identify the dominant
minutes/hours phase of a complete source-to-checkpoint ingest.

`scripts/benchmark_complete_tranche_phases.py` executes the existing tranche
runner in-process and interposes only on `PhaseReceipt` construction. A receipt
is constructed immediately after its phase work, so consecutive receipt
completions delimit the wall interval spent reaching each phase. The semantic
runner and semantic receipt identity are unchanged.

This is stronger than polling `tranche_run_state.json`: even two very fast phases
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

The report feeds the same absolute-wall optimization policy used by
`src/runtime/performance_attention.py`. Hours outrank minutes, minutes outrank
seconds, and a long phase that should not exist in production remains high
priority until it is actually removed or bypassed.

Example shape:

```text
python scripts/benchmark_complete_tranche_phases.py \
  --tranche GWB \
  --output-root /path/to/output \
  --database-url postgresql://... \
  --strict-exact
```

Arguments not owned by the timing wrapper are passed through to
`run_complete_tranche.py`.

For a genuinely fresh full-ingest measurement, use a fresh output root. On a
resumed run, checkpoint-loaded `PhaseReceipt` objects are not charged as newly
executed phases.

This is execution observability only. Timing values never participate in phase
receipt identity or semantic authority.
