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
- There are exactly two active local branch names: `main` and
  `agent/packed-a2-swar`.
- Unassigned branch tips are archived under `refs/archive/local/`; they are
  retained for recovery but are not active development branches.
- The former owner/handoff, hot-path, demand-trigger, and strict-runtime tips
  are preserved there. Their worktrees are detached so their `.tmp/` evidence
  and, for H9, tracked changes remain recoverable without presenting as active
  development lines.
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

Do not remove a worktree with uncommitted changes. The former H9 worktree
contains tracked changes and is intentionally retained in detached state.
The other detached worktrees contain preserved `.tmp/` runtime evidence; they
may be removed only after that evidence is explicitly copied or confirmed
elsewhere.

## Weld record

The four retired local branch tips were compared with the canonical branch.
The owner/handoff, hot-path, and demand-trigger tips are strict ancestors of
the canonical implementation. The strict-runtime tip has historical commits
not represented by hash, but its surviving changes are an older progress and
instrumentation variant superseded by the canonical runtime surfaces; no
unverified cherry-pick was performed. All four tips remain recoverable at:

```text
refs/archive/local/agent/owner-handoff-performance
refs/archive/local/agent/owner-hot-path-optimisations
refs/archive/local/agent/demand-trigger-target-provenance
refs/archive/local/agent/strict-runtime-485-487
```

Remote branches are intentionally unchanged and require a separate explicit
cleanup decision.
