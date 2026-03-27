# JSON Artifact Boundary

Date: 2026-03-27

Purpose: make the repo's "canonical sqlite" doctrine precise by separating
runtime canonical storage from fixtures, examples, source packs, demo outputs,
and temporary diagnostics.

## Core rule

For the fact-intake / fact-review / semantic-promotion lanes, the canonical
receiver is SQLite read models. JSON may still exist in the repo, but not every
JSON file is a canonical runtime store.

## Allowed JSON families

1. Fixtures
- `tests/fixtures/**`
- Purpose: deterministic regression and acceptance coverage
- Not canonical runtime state

2. Examples / contracts / schemas
- `examples/**`
- `schemas/**`
- Purpose: interface documentation and minimal seed payloads
- Not canonical runtime state

3. Data seeds / source packs / profiles
- `data/**`
- `policies/**`
- Purpose: static inputs, vocab, bridge seeds, profiles, and source-pack definitions
- These may be authoritative inputs, but they are not runtime fact-review state

4. Demo and benchmark artifacts
- `demo/**`
- selected `sl_zelph_demo/**`
- Purpose: reproducible demos, benchmark slices, and report outputs
- Not canonical runtime state

5. Cache / temp / diagnostics
- `.cache_local/**`
- `/tmp/**`
- Purpose: transient diagnostics, local caches, one-off report outputs
- Never treat these as canonical unless explicitly imported/persisted

## Canonical runtime families

These are the families where "single source sqlite" is the correct runtime
statement:

- fact intake / fact review / semantic refresh surfaces in `itir.sqlite`
- DB-backed wiki timeline / AAO runtime hydration
- DB-backed chat archive / messenger / OpenRecall browse surfaces

## Current exception boundary

Some review/report builders still emit JSON/markdown artifacts as their primary
output contract:

- affidavit coverage review
- contested Google Docs narrative review
- broader diagnostics / scorecards / comparison reports

These are currently mixed review surfaces:

- affidavit coverage review now has a narrow canonical sqlite receiver for
  normalized runs/rows/facts when persisted through the read-model path
- contested Google Docs narrative review inherits that receiver when the
  builder is invoked with `--db-path`
- the JSON/markdown artifacts remain valid derived projections and a
  presentation/export contract
- broader diagnostics / scorecards / comparison reports remain artifact-backed

## UI/runtime rule

- If a persisted sqlite/read-model path exists, UI routes must prefer it.
- Fixtures may support tests and demo fallback, but not primary runtime
  hydration for canonical personal-result views.
- Artifact-backed routes must state that they are artifact-backed.

## Immediate repository consequence

- `itir-svelte /corpora/processed/personal` is now DB-first for persisted
  `:real_` fact-review runs.
- Affidavit review now has a canonical persisted receiver for normalized
  sqlite storage, but existing artifact cards remain useful derived
  projections until the UI is switched to prefer the persisted lane.
