# Ontology Versioning for WrongTypes, Remedies, and ValueFrames

This guide explains how to evolve the ontology without breaking downstream
consumers. It supplements the document-oriented versioning model and focuses on
domain entities (`WrongType`, `Remedy`, and `ValueFrame`) that surface directly
in APIs and inference outputs.

## Version model

- Use **semantic versioning** for each ontology entity: `MAJOR.MINOR.PATCH`.
  - **MAJOR** – structural or meaning-breaking changes (renamed scopes,
    materially different doctrine, or removal of required associations).
  - **MINOR** – additive changes (new aliases, optional metadata fields,
    additional source links, or supplementary examples) that remain backwards
    compatible.
  - **PATCH** – documentation-only fixes and typo corrections with no schema or
    semantic impact.
- Persist the current version on the entity row (`version` column) and store
  provenance for the change (`updated_at`, `updated_by`, `change_notes`).
- Treat `WrongTypeSourceLink` updates as part of the parent `WrongType` version
  because they alter the authoritative grounding.

## Migration and backwards-compatibility expectations

- **MAJOR increments**
  - Add a new row with a new primary key; never rewrite historical records.
  - Provide a `supersedes_id` pointer so inference outputs and application code
    can map legacy references forward.
  - Ship a migration script that backfills existing `WrongTypeInstance` or
    `EventRemedy` records to the new row while retaining the legacy link for
    audit queries.
- **MINOR increments**
  - Update the existing row in place and record the change notes.
  - Avoid tightening constraints that would invalidate stored
    `WrongTypeInstance`, `RemedyChoice`, or `ValueFrameEvaluation` rows.
  - Maintain alias tables (`wrong_type_alias`, `remedy_alias`, `value_frame_alias`)
    so text-based resolvers remain stable.
- **PATCH increments**
  - Prefer documentation updates; if data must change, ensure the migration is a
    no-op for downstream foreign keys (e.g., correcting spelling in `display`
    fields only).

## Operational safeguards

- Attach **change windows** for MAJOR releases so API clients can pin to a
  version and schedule migrations.
- Run **data snapshots** before and after migrations; store diffs alongside the
  migration manifest.
- Require **dual approval** (ontology + data engineering) for MAJOR and MINOR
  bumps to ensure taxonomy, provenance, and performance expectations are met.
- Keep **deprecation ledgers** that enumerate legacy IDs and their
  replacements; expose them via an API endpoint to support consumer rollouts.

## Examples

- **WrongType MAJOR**: Splitting a broad "economic abuse" WrongType into
  "coercive control" and "financial deprivation". Create two new rows,
  deprecate the original, migrate existing instances to their closest match,
  and record `supersedes_id` relationships.
- **Remedy MINOR**: Adding `apology` as a new `RemedyOption` for a defamation
  WrongType. Update the row in place, append to alias tables, and refresh
  recommendation weights without altering historical remedies.
- **ValueFrame PATCH**: Fixing a typo in a value frame label while leaving the
  semantic axes untouched; update display labels only and leave foreign keys
  unchanged.
