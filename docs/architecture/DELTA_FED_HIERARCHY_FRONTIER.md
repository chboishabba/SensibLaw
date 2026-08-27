# Delta-fed hierarchy frontier reduction

The measured hierarchy owner is a runtime instance of the DASHI PNF boundary
contract, not an independent semantic architecture.

The relevant formal owners are:

- `DASHI/Cognition/PNF/ParentInterfaceReduction.agda`;
- `DASHI/Cognition/PNF/SparseFibredFrontier.agda`;
- `DASHI/Cognition/PNF/BoundedInterfaceSketch.agda`;
- `DASHI/Cognition/PNF/BoundedMDLPlanner.agda`.

The runtime correspondence is:

```text
closed child boundary
-> canonical sparse parent reducer
-> admitted parent exports
-> lookup projection of admitted exports
-> reductive parent measure
```

Migration 062 already owns that fused per-parent semantic reducer in
`execution.rebuild_numeric_pnf_parent_frontier`. It aggregates already-compressed
child actor fibres and child exports, retains unresolved typed demands, rebuilds
lookup only for admitted parent exports, records explicit frontier outcomes, and
updates the parent interface measure plus reduction receipt.

The performance defect addressed by migrations 196-198 is therefore orchestration
around that reducer rather than a missing semantic reducer.

## Deferred hierarchy construction

`numeric_hierarchy_planner.py` establishes the transaction-local setting:

```text
sensiblaw.defer_frontier_rebuild=on
```

Migration 196 makes the sparse-frontier close trigger honor that boundary. Parent
interfaces may be constructed during hierarchy materialization without eagerly
running the expensive frontier reducer for every region closure. Ordinary
non-deferred region closure retains the historical trigger semantics.

## Affected-key document frontier

Migration 197 turns `semantic_pnf_frontier_reduction_receipt` into an explicit
affected-key witness. A non-leaf interface is dirty when:

- it has no reduction receipt;
- its graph revision differs from the certified revision;
- a direct child closed after the parent reduction; or
- a direct non-leaf child frontier was reduced after the parent reduction.

Dirty interfaces are closed upward through `parent_interface_id`. The existing
canonical sparse parent reducer then runs only on that affected frontier in
bottom-up region order.

This is the runtime shape:

```text
Delta child boundary
-> dirty interface keys
-> upward affected-parent closure
-> canonical local parent reducer
-> sparse boundary publication
```

A topology-only change to a child's `parent_interface_id` is not by itself a
semantic dirty seed for the child's own boundary. Ancestor/topology publication
owns that relation separately.

## Timing

Migration 198 preserves every invocation of the existing frontier stage receipt
in `semantic_pnf_frontier_stage_sample`. The summary receipt remains compatible;
the sample table is execution observability only and does not participate in
semantic authority or portable parity.

`scripts/diagnose_hierarchy_frontier_timing.py` reports:

- each frontier-stage invocation and affected-interface count;
- per-region-kind reducer count;
- summed/average/max reducer milliseconds;
- input and output frontier cardinality.

This lets a hierarchy timing be decomposed into actual sparse frontier work versus
remaining hierarchy construction/planning overhead.

## Representative performance floor

The 95-sentence / 2,522-token fixture remains useful for B1, hierarchy and parity
regressions, but it is too small to establish representative post-parser ranking.

`src/runtime/performance_workload_scale.py` therefore sets the immediate floor at:

```text
>= 25,000 parsed tokens
```

across one controlled benchmark corpus. Multiple document receipts may compose to
that total. Below the floor, semantic and kernel regression claims remain valid,
but the run must not be labelled representative performance evidence.

Use:

```bash
python scripts/check_representative_performance_workload.py \
  receipt-1.json receipt-2.json ...
```

Exit status is 0 for representative scale, 2 for measured-but-too-small, and 3
when token volume is unknown.

The immediate acceptance goal remains total strict numeric source-to-authority
wall time no greater than 1.5x bare spaCy on the same controlled workload. The
stronger repository target remains post-parser occupancy no greater than 0.10x
spaCy.
