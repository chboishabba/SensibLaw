# Wikidata Nat Cohort E: Unreconciled `instance of`

Date: 2026-04-02

## Change Class

Standard change.

## Purpose

Make Nat Cohort E explicit as a bounded governance/reconciliation-deficit
bucket and pin the next gate as review-first.

This artifact is lane-local to Cohort E.

## Scope

In scope:

- Cohort E only: subjects whose `instance of` could not be reconciled
- explicit governance posture for this cohort
- one review-first next gate

Out of scope:

- Cohort B, Cohort C, Cohort D
- execution expansion
- shared progress counters

## Source Alignment

Source mapping note:

- `SensibLaw/docs/planning/wikidata_nat_wdu_sandbox_migration_mapping_20260401.md`

Inherited Cohort E bucket:

- `142` statements with unreconciled `instance of`

## Cohort Definition

- lane id: `wikidata_nat_cohort_e_unreconciled_instanceof`
- cohort type: `governance_reconciliation_deficit`
- expected handling: `review_only`
- migration default: `hold`

## Review-First Next Gate

Pinned next gate:

- `review_first_reconciliation_scan`

Gate intent:

- classify unreconciled typing causes before any migration decision
- keep statement-bundle semantics visible while typing remains unreconciled
- surface unresolved typing as explicit review pressure, never silent fallback

Gate exit condition:

- each row is either:
  - mapped to a reconciled typing path and promoted to a different cohort, or
  - retained in Cohort E with an explicit hold rationale

## Governance

- Cohort E is not an execution lane.
- No unreconciled `instance of` row should be treated as checked-safe by default.
- Reconciliation deficit is a first-class reason to hold.

## Compact ZKP

### O

- Nat lane reviewers
- ontology-group reviewers

### R

- isolate unreconciled typing into one explicit review bucket

### C

- this lane-local Cohort E artifact only

### S

- Cohort E is already identified in the Nat mapping note as 142 rows

### L

- unreconciled typing -> review-first scan -> reconcile-or-hold

### P

- pin one explicit review-first gate for Cohort E

### G

- no promotion from unreconciled typing without reconciliation path

### F

- unresolved typing prevents safe cohort promotion until reconciled or held

