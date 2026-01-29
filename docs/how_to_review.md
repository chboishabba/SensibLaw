# How to Review (Human, Non-Semantic)

This workflow is for **inspection and annotation only**. It must not introduce reasoning or compliance judgments.

## What you do
- Read extracted obligations, activation results, and cross-doc topology.
- Add human notes or disagreement markers as metadata.
- Export bundles for audit.

## What you do *not* do
- Decide compliance or precedence.
- Infer meaning or add defaults.
- Edit obligation text or identities.

## Workflow
1. Load a ReviewBundle JSON into the UI.
2. Inspect obligations verbatim.
3. Inspect activation (if present).
4. Inspect cross-doc edges (explicit only).
5. Add notes or disagreements if needed.
6. Export the bundle.

## Rules
- Notes are metadata only; removing them yields identical hashes.
- No summarisation or auto-fixups.
- If something seems missing, record a note—do not change payloads.

## Red flags
- UI suggesting conclusions (“therefore”, “means that”).
- Auto-generated summaries.
- Hidden defaults or inferred fields.

If you see a red flag, stop and file an issue.
