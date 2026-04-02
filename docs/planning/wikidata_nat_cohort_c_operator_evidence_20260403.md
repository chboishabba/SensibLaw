# Wikidata Nat Cohort C Operator Evidence Packet Extension

Date: 2026-04-03

## Purpose

Strengthen the Cohort C operator evidence surface by packetizing a broader live-preview result set with richer policy-risk annotations. This maintains the review-first, fail-closed posture while providing operators a clearer next gate for any classification or pilot actions.

## Context

- Builds off the existing Cohort C scan plan (`wikidata_nat_cohort_c_population_scan_20260402.md`), live preview extension, and CLI operator packet entrypoints.
- This artifact does not change Cohort B/D/E or introduce automation; it simply documents the next operator-facing packet that wraps the current preview fixture with traceable holds.
- The lane keeps `progress_claim: reviewable_packet` and `promotion_guard: hold` for every row.

## Inputs

- Extended preview fixture: `tests/fixtures/wikidata/wikidata_nat_cohort_c_operator_packet_extension_20260403.json`
- Operator CLI: `sensiblaw wikidata cohort-c-operator-packet`

## ZKP Frame

### O

- Operators reviewing policy-risk evidence before any type resolution
- Nat reviewers overseeing Cohort C hold decisions

### R

- deliver an operator packet that a) cites a broader set of preview candidates and b) annotates each row with hold reasons, reference anchors, and qualifier notes
- keep the lane fail-closed by logging policy concerns per row
- provide a clear next gate: confirm policy risk before any migration planning

### C

- Cohort C branch/scan/live preview artifacts
- this new operator packet extension doc plus the fixture
 
### S

- preview helper and CLI exist; this extension simply clarifies evidence packaging
- each candidate remains tied to `review_first_population_scan`
- operators must reference the fixture when running follow-up triage

### L

1. produce a broader sample from the existing non-GHG/missing `P459` selector
2. package the sample into the operator packet fixture with hold metadata and evidence links
3. refer to the fixture in CLI/packet notes so the evidence remains reproducible

### P

- extend the fixture to include `reference_anchor`, `qualifier_hint`, and
  `operator_hold_reason` for each candidate
- require the operator packet to cite the fixture hash plus CLI command that
  produced it
- confirm each row remains under `promotion_guard: hold`

### G

- no automation claims; the packet is for operator review only
- each row documents why the hold remains (`preview_hold_reason` plus
  `operator_hold_reason`)
- keep policy-risk gate `review_first_population_scan`

### F

- this is a documentation/evidence step; any further automation requires
  explicit bridge-out guidance in future docs

## Operator Notes

1. Use the fixture to inspect reference anchors before updating classification logs.
2. Keep `promotion_guard: hold` until a second reviewer confirms the policy risk is mitigated.
3. Log CLI execution (`sensiblaw wikidata cohort-c-operator-packet`) as part of the fix-it review so the packet ties back to the documented fixture.

## Runtime Seam

- The new helper `build_nat_cohort_c_operator_evidence_packet` (see `src/ontology/wikidata_cohort_c_operator_evidence.py`)
  deterministically materializes this richer evidence packet from any Cohort C preview payload.
- Use `sensiblaw wikidata cohort-c-operator-evidence` to rerun the preview helper, regenerate the fixture, and append the packet hash so operators can confirm the data slice.
- Run `sensiblaw wikidata cohort-c-operator-report` (or point it at the generated evidence packet via `--input`) to materialize the derived hold/reference summary that operators cite in downstream review logs.
- Run `sensiblaw wikidata cohort-c-operator-report-batch --inputs <file1> <file2> ...` to merge several evidence packets into one batch summary, keeping every candidate clearly held under the same gating semantics.
- The CLI command shares the same fail-closed gate (`review_first_population_scan`) and respects the `promotion_guard: hold` semantics so the evidence remains a review artifact.
