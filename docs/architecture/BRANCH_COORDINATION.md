# SensibLaw branch coordination

## Canonical development branch

The active implementation branch for the numeric/P​​NF work is:

```text
agent/packed-a2-swar
```

All new implementation, migration, benchmark, and certification work for
that stream starts from and is pushed to this branch. Its companion formal
repository is tracked separately and is out of scope for this coordination
surface.

## Branch policy

- `agent/packed-a2-swar` is the canonical active branch.
- `main` is the integration baseline.
- Existing checked-out branches remain assigned to their worktrees until
  their owners explicitly release them.
- Unassigned local branches are archived under `refs/archive/local/`; they are
  retained for recovery but are not active development branches.
- Remote branches are not deleted by local cleanup. Remote deletion requires a
  separate explicit ownership decision.
- `.tmp/` runtime evidence is preserved and is not treated as source changes.

## Current operational state

```text
SensibLaw HEAD: agent/packed-a2-swar
Current commit: see `git rev-parse HEAD`
Database migrations: 210/210 on the certification database
Current experiment: 16K exact-work budget diagnostic
Acceptance status: incomplete; the 600-second corpus run timed out
```

## Worktree rule

Do not remove a worktree with uncommitted changes. In particular, the H9
admission worktree contains tracked changes and is intentionally retained.
Clean detached scratch worktrees may be removed after their evidence has been
confirmed elsewhere.
