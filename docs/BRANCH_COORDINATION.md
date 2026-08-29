# SensibLaw branch coordination

## Canonical target

All active SensibLaw implementation work targets:

```text
agent/packed-a2-swar
```

Its remote-tracking branch is `origin/agent/packed-a2-swar`. Pull it before
starting work and push completed changes back to that branch.

`main` is the integration/root branch. It is not the active optimization target.

## Historical branches and worktrees

Branches named for older experiments, PR recoveries, or owner handoffs are
historical evidence unless explicitly promoted. Do not merge them wholesale
into the canonical branch. Compare resulting trees and transplant only a
verified missing change.

Detached worktrees are inspection snapshots, not active development targets.

## Required handoff

Every runtime handoff should state:

- canonical branch;
- exact HEAD commit;
- whether the checkout is ahead/behind its remote;
- tests and live database runs actually executed;
- database endpoint and whether it was disposable.

Do not treat a commit hash in a report as authoritative until the remote branch
and local checkout have been verified.
