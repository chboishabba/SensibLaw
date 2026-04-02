# Cohort E Diagnostics CLI

Date: 2026-04-03

## Purpose

Provide a bounded operational surface so reviewers can regenerate the Cohort E
diagnostic report from the sample axis fixture without touching shared scripts.

## Usage

```
sensiblaw cohort-e-diagnostics \
  --samples SensibLaw/tests/fixtures/wikidata/wikidata_nat_cohort_e_split_axis_sample_20260403.json \
  --output SensibLaw/tests/fixtures/wikidata/wikidata_nat_cohort_e_diagnostic_report_20260403.json
```

This command reruns the helper, keeps the lane hold-only, and reproduces the
fixture for auditing. Use `--batch` to emit a series of diagnostic reports
(simulating repeated review runs) and compare them against
`SensibLaw/tests/fixtures/wikidata/wikidata_nat_cohort_e_diagnostic_batch_report_20260403.json`.
The summary file now records aggregated disagreement counts (see
`SensibLaw/tests/fixtures/wikidata/wikidata_nat_cohort_e_diagnostic_summary_20260403.json`)
so repeated batch runs yield a broader evidence surface. Pass multiple summary
paths with `--summaries` and provide `--index-output` to produce the lane-local
summary index fixture at `SensibLaw/tests/fixtures/wikidata/wikidata_nat_cohort_e_summary_index_20260403.json`.
The `--summary-output` option now writes grouped disagreement tallies (see
`SensibLaw/tests/fixtures/wikidata/wikidata_nat_cohort_e_diagnostic_summary_20260403.json`)
so reviewers can quickly see axis-level pressure.

## Governance

- the CLI is explicit that Cohort E is still review-first and non-promoting
- outputs stay marked `non_authoritative` and retain the `hold_reason`
