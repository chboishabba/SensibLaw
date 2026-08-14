# Incremental closure-owner handoff

## Scope

This change is execution-only. It does not alter proposal identity, semantic
owner identity, admission order, reduction semantics, residual semantics, or the
fixed-point criterion.

The runtime previously stored replay history twice on every new event:

1. `_append_replay_event` copied the complete artifact-ref tuple and complete
   event tuple before appending one member;
2. `_write_closure_handoff_checkpoint` embedded every accumulated event/artifact
   ref in the next atomic JSON checkpoint.

For `E` replay events, that makes bookkeeping copy/serialization work grow like
`sum(1..E)`, i.e. O(E^2), even when semantic work per event is bounded.

## v3 physical carrier

`closure-owner-replay:v3` separates cold append-only replay history from the hot
current frontier:

```text
immutable replay artifact
        |
        v
one compact journal event  ---- append O(1)
        |
        v
small atomic frontier checkpoint
```

The journal stores only:

- sequence number;
- artifact kind;
- artifact ref;
- previous event digest;
- event digest.

The atomic frontier checkpoint stores the current owner revision/frontier,
activation progress, recorded delta refs, and the journal count/digest. It does
not embed the cumulative proposal/receipt/reduction event history.

On resume, the journal digest chain is verified and its events are materialized
once for deterministic owner reconstruction. Those temporary replay lists are
removed from hot state after reconstruction.

If a process dies after a journal append but before the corresponding frontier
checkpoint is atomically replaced, that uncheckpointed journal tail is truncated
on resume and deterministically recomputed. No partial owner state is guessed.

## Identity caching

The owner hot path repeatedly probes/sorts immutable content-addressed objects.
`FactorProposal`, `OwnerKey`, `ObservationDelta`, `SolverJob`, and
`SolverReceipt` now cache their canonical ref after its first computation. Their
semantic payload remains unchanged.

## Formal boundary

No new Agda theorem is required for this tranche because the transformation is
observationally the identity on semantic execution:

```text
same immutable inputs
same canonical event order
same replay artifacts
same owner reconstruction
same reduced factors/residuals
```

The next planned performance step is different: evaluating independent
`OwnerKey` reductions concurrently and committing their results canonically.
Before implementing that step, the required commutation/independence condition
should be checked against the Agda execution/dynamic-safety contracts (and added
there if it is not already explicit). Parallel physical execution must be
justified by semantic independence, not merely by available cores.

## Telemetry

The existing closure amplification receipt automatically exposes the new
counters:

- `handoff_journal_events`;
- `handoff_journal_append_ns`;
- `handoff_compact_checkpoints`;
- `handoff_compact_checkpoint_ns`;
- `handoff_checkpoint_replay_rows_serialized` (zero under v3);
- `handoff_uncheckpointed_tail_bytes` when recovery discards an uncommitted tail.

`SENSIBLAW_CLOSURE_JOURNAL_FSYNC_INTERVAL` defaults to `0`, matching the
process-crash durability class of the previous atomic JSON writer. A positive
value requests an `fsync` every N journal events when stronger machine/power-loss
durability is required.
