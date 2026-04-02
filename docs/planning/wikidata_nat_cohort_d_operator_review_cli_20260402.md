# Wikidata Nat Cohort D Operator Review CLI

Date: 2026-04-02

## Purpose

Add a bounded, non-executing CLI surface that materializes the Cohort D
operator/reviewer queue from a Cohort D type-probing artifact.

## Command

- `sensiblaw wikidata cohort-d-operator-review --input <type_probing.json> [--output <operator_review.json>]`

## Behavior

- reads a Cohort D type-probing surface JSON
- builds a Cohort D operator/reviewer queue surface
- emits summary when `--output` is used:
  - schema version
  - readiness
  - queue size
  - unresolved packet-ref count

## Governance

- fail-closed and non-executing
- `automation_allowed=false`
- `can_execute_edits=false`
- no direct migration execution

## Non-Claims

- this command does not perform reconciliation edits
- this command does not promote checked-safe rows
- this command only packages review queue state for operator use

