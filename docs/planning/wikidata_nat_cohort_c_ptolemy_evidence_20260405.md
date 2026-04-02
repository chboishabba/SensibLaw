# Wikidata Nat Cohort C Ptolemy Evidence Slice

Date: 2026-04-05

## Purpose

Push the Ptolemy lane by recording a broader operator evidence slice for Cohort C derived from multiple live-preview rows, keeping the lane review-first and fail-closed. This note clarifies how the new sample should be treated, how it feeds into the existing CLI reporter/batch workflows, and what operators must log.

## Inputs

- Extended evidence fixture `tests/fixtures/wikidata/wikidata_nat_cohort_c_operator_evidence_packet_20260404.json`
- New broader fixture `tests/fixtures/wikidata/wikidata_nat_cohort_c_ptolemy_evidence_sample_20260405.json`
- CLI entrypoints: `sensiblaw wikidata cohort-c-operator-evidence` and `sensiblaw wikidata cohort-c-operator-report-batch`

## Ptolemy Operator Surface

- The new fixture mirrors a broader live-preview slice (3+ candidates) with per-candidate `reference_anchor`, `preview_hold_reason`, `operator_hold_reason`, and `qualifier_hint` statements.
- Operators feed the evidence fixture into `sensiblaw wikidata cohort-c-operator-report-batch` along with previously generated packets to produce an aggregated hold/reference summary that always stays within the review-first gate.
- The aggregate summary can be published as governance evidence; every row retains `promotion_guard: hold` and `hold_gate: review_first_population_scan`.

## Live-Preview/Runtime Boundary

- This sample is derived from deterministic runs of the existing live preview helper; the fixture is a snapshot of those rows, so rerunning the preview should reproduce the candidate set when the query results are stable.
- No automation or migration claims are made; operators must rerun the preview helper if they suspect the dataset has drifted before reusing the batch report.
