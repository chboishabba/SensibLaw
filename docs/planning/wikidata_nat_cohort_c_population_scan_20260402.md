# Wikidata Nat Cohort C Population Scan Plan

Date: 2026-04-02

## Purpose

Advance the non-GHG-protocol / missing `determination method (P459)` lane toward
its first review-first population scan so the policy-risk cohort is bound into
the repo rather than remaining an abstract branch note.

The runtime now has a bounded Cohort C scan normalizer for the pinned sample
fixture, but the live population scan gate remains unopened.

This artifact stays within Cohort C: it reuses the migration mapping plan from
`wikidata_nat_wdu_sandbox_migration_mapping_20260401.md` and the pinned branch
state from `wikidata_nat_cohort_c_branch_20260401.md` and does not reach into
Cohort B/D/E.

## Inputs

- `SensibLaw/docs/planning/wikidata_nat_wdu_sandbox_migration_mapping_20260401.md`
- `SensibLaw/docs/planning/wikidata_nat_cohort_c_branch_20260401.md`
- `SensibLaw/tests/fixtures/wikidata/wikidata_nat_cohort_c_population_scan_20260402.json`

## ZKP Frame

### O

- Nat lane reviewers
- ontology workgroup reviewers
- Cohort C policy-risk branch surface
  
### R

- conduct a bounded extraction of statements where `P459` is missing or not
  the GHG protocol
- capture a short set of candidate rows that can be reviewed before any
  execution claim
- record the scan plan so it can be re-run with real data

### C

- the existing Cohort C branch artifact
- the sandbox migration mapping note that defines policy-risk families
- this plan document plus the attached population-scan fixture

### S

- Cohort C selection rule is already pinned
- the sandbox page defines the qualifier/reference expectations
- no actual live population scan has run yet
- the runtime scan normalizer exists for the pinned sample fixture

### L

1. capture the policy-risk branch state (`branch_pinned`)
2. plan a first review-first population scan (this document)
3. normalize the pinned sample fixture into a review-first Cohort C surface
4. generate per-statement scan results and hold them in a review-only surface

### P

- run the `non_ghg_protocol_or_missing_p459` selection rule against the `P5991`
  source fixture, filter the results, and persist a review-only candidate set
- ensure each candidate records whether `P459` was absent or present but
  non-GHG, plus a short annotation of its qualifier shape

### G

- stay fail-closed: do not pretend this scan is a migration step, just a
  discovery artifact
- keep the review-first gate (next gate: `review_first_population_scan`)

### F

- Cohort C exists only as a policy branch; this artifact begins the work
  toward populating it with reviewable candidates

## Candidate Summary

The attached fixture lists a small, bounded sample of statements flagged by the
selection rule. Each row captures the tabular key (`qid`, `label`), the
`p459_status` (missing vs non-GHG), and the qualifier/reference shape that must
be verified during the scan.

## First Review-First Scan Steps

1. Run the `non_ghg_protocol_or_missing_p459` selector on the `P5991` statements
   from `wiki_revision_nat_wdu_sandbox_p5991_p14143_20260401.json`.
2. For each row, record the candidate `qid`, label, and whether `P459` is
   missing or not the GHG protocol in the lane-local fixture.
3. Surface the qualifier/reference annotations alongside the scan results so
   reviewers can focus on policy risk.
4. Use this document plus fixture to steer the first review-first inspection
   before granting any classification or export gate.

## Next Gates

- `review_first_population_scan` (documented candidate set)
- `review_first_population_scan_ready` (runtime normalizer surface)
- future packetized review surface once the scan yields reproducible rows
