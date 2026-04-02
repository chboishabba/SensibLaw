# Wikidata Nat Cohort C Live Preview Extension

Date: 2026-04-02

## Purpose

Push the next Cohort C step by expanding the live preview coverage for the
non-GHG or missing `determination method (P459)` lane, improving the operator
packet evidence while keeping every artifact review-first and fail-closed.

## Context

- Builds on `wikidata_nat_cohort_c_population_scan_20260402.md` (review-first scan
  plan) and the pinned branch artifact `wikidata_nat_cohort_c_branch_20260401.md`.
- This extension stays entirely within Cohort C and does not influence Cohort
  B/D/E semantics or shared repo-wide policy documents.
- Cohort C already has a live preview helper and operator packet; this artifact
  covers the next highest-yield step: a broader live preview sample plus
  explicit operator routing cues that emphasize the lane remains review-only.

## Inputs

- Cohort C population scan fixture: `tests/fixtures/wikidata/wikidata_nat_cohort_c_population_scan_20260402.json`
- New live preview fixture: `tests/fixtures/wikidata/wikidata_nat_cohort_c_live_preview_extension_20260402.json`
- Operator packet CLI entrypoint: `sensiblaw wikidata cohort-c-operator-packet`

## ZKP Frame

### O

- Nat lane reviewers engaging with Cohort C preview results
- Operators rerunning gateway preview scans
- Governance leads tracking policy-risk buckets

### R

- broaden the live preview sample so operators can verify that P459 is not
  the GHG protocol or is missing across more candidates
- surface per-candidate evidence (`p459_status`, qualifiers, references) inside
  a small lane-local fixture that the operator packet can cite
- keep the lane fail-closed by binding every preview row to a hold/review gate

### C

- Cohort C branch and scan plan artifacts
- this document and the new live preview fixture
- runtime preview helper invoked via CLI, producing operator packet evidence

### S

- the selection rule is locked to Cohort C statements
- preview helper already gated to fail-closed and review-first
- operator packet surfaces demand explicit hold reasons before any promotion

### L

1. reuse the selection rule from the scan plan to gather a broader preview sample
2. package the sample into the lane-local fixture plus CLI packet
3. surface the fixture to operators while enforcing hold/review metadata

### P

- run the `non_ghg_protocol_or_missing_p459` preview helper across additional
  segments of the sandbox `P5991` statements
- for each candidate emit `p459_status`, `preview_hold_reason`, qualifier hints,
  and reference pointers in the lane-local fixture
- extend the operator packet to cite the fixture and clarify that each row
  remains under a `review_first_population_scan` promise

### G

- no automation claims; preview remains a discovery artifact
- all preview rows carry `promotion_guard: hold` plus a documented
  `preview_hold_reason`
- lane stays disjoint from Cohort B/D/E while feeding operator review lanes

### F

- preview samples remain narrow; this extension scales coverage without
  opening promotion claims

## Operator Guidance

1. Use the preview fixture to answer: “Which qualifiers or references reinforce
   that `P459` is missing or non-GHG?” Document answers inside
   `preview_hold_reason`.
2. Keep `progress_claim` anchored to `reviewable_packet` and require a second
   reviewer to confirm any typing/anomaly before the packet leaves review.
3. Log the CLI command plus fixture hash when annotating the cohort’s review log
   so follow-up scans trace the same data slice.
