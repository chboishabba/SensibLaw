# Wikidata Nat Cohort D Review Lane

Date: 2026-04-02

## Lane Assignment

- Lane: Nat Cohort D only
- Scope: statements flagged in `SensibLaw/docs/planning/wikidata_nat_wdu_sandbox_migration_mapping_20260401.md`
  under **Cohort D: subjects with no `instance of`** (1395 statements in the sandbox slice).

## Purpose

Frame Cohort D as a review-first bucket that reuses the Nat packet grammar while explicitly deferring migration execution. The lane should remain low-risk, disjoint from Cohorts B/C/E, and keep governance gates focused on typing clarity before promotion.

## Packet Shape

- Lane-local reviewers craft packets with the standard Nat reviewer-packet fields but restrict `progress_claim` to `reviewable_packet` and include a `promotion_guard` set to `hold` by default.
- Required special notes:
  - `subject_typing_gap`: reason why the subject lacks `instance of`.
  - `suggested_typing_anchor`: any adjacent surface (related statements, qualifiers, references) that could supply typing candidates.
  - `scan_plan_note`: enumerated checks (e.g., "confirm subclass path via P279", "inspect same-namespace summaries") that reviewers should cover before re-raising the packet.
- `governance_flags` continue to include `automation_allowed:false` and `fail_closed` to signal this lane stays review-controlled.

## Gate and Next Step

The next gate for Cohort D is a dedicated typing-resolution review step:

1. Confirm the subject truly lacks `instance of` by verifying the sandbox snapshot and adjacent query hits.
2. Document any plausible type candidates in `suggested_typing_anchor`.
3. Once a reviewer has enumerated at least one typing candidate and assessed references/qualifiers, update `promotion_guard` to `revisit_after_typing` and signal the packet as ready for a lightweight `type-probing scan` that keeps the lane review-first.

`type-probing scan` is a bounded note (markdown or JSON) stored alongside the packet describing which properties or claims were checked; it does not trigger downstream automation but ensures a documented follow-up path.

## Review Guidance

- Keep Cohort D packets isolated from other cohorts: do not reuse the same packet data for B/C/E lanes.
- Reviewers explicitly log their gating decisions inside the lane-local artifact before any promotion claim, so downstream workloads understand this bucket remains review-first.
