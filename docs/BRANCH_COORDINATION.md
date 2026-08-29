# SensibLaw branch coordination

## Canonical target

All active SensibLaw implementation work targets:

```text
agent/packed-a2-swar
```

Its remote-tracking branch is `origin/agent/packed-a2-swar`. Pull it before
starting work and push completed changes back to that branch.

`main` is the integration/root branch. It is not the active optimization target.

## Formal companion target

Parser streaming, direct packed-fibre execution, semantic delta transport,
hierarchy/reconciliation, stable evidence, and production authority work must
also inspect the corresponding formal owners in:

```text
chboishabba/dashi_agda
```

The current active formal synthesis is on `agent/delta-native-parent-frontier`
until promoted/merged. In particular check:

- `StreamingSemanticPacmanKernelExact.agda`
- `DeltaNativePNFDreamFlowExact.agda`
- `FibreSolverDeltaStreamExact.agda`
- `DirectDeltaCompilerArchitectureExact.agda`
- `DirectDeltaCompilerActivationExact.agda`
- `DirectStreamingRoadmapSynthesisExact.agda`

SensibLaw and DASHI are separate repositories but this execution architecture
is one cross-repository contract. A runtime handoff is incomplete if it changes
that contract without stating whether the Agda owners were checked and whether
they remain aligned.

The temporal invariant to preserve is:

```text
state(prefix ++ suffix) = continue(state(prefix), suffix)
```

The runtime must converge on current authority plus unresolved frontier, not a
retained parser history that is recompiled after EOF.

## Historical branches and worktrees

Branches named for older experiments, PR recoveries, or owner handoffs are
historical evidence unless explicitly promoted. Do not merge them wholesale
into the canonical branch. Compare resulting trees and transplant only a
verified missing change.

Detached worktrees are inspection snapshots, not active development targets.

## Required handoff

Every runtime handoff should state:

- canonical SensibLaw branch;
- exact SensibLaw HEAD commit;
- whether the checkout is ahead/behind its remote;
- tests and live database runs actually executed;
- database endpoint and whether it was disposable;
- Agda branch/ref inspected for semantic-runtime work;
- Agda files/theorems affected or relied upon;
- whether the formal and runtime contracts are aligned, stale, or intentionally
  awaiting a follow-up.

Do not treat a commit hash in a report as authoritative until the remote branch
and local checkout have been verified.
