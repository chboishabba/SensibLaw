# Wikidata Nat Cohort C Operator Index

Date: 2026-04-06

## Purpose

The Ptolemy lane’s next step is to produce a deterministic operator index over the broader Cohort C evidence slices so governance reviewers can compare qualifiers and references without promoting the lane. The index summarizes hold reasons, reference anchors, and candidate-level gates while preserving the failure posture (`promotion_guard: hold`).

## Inputs

- Evidence packets such as `tests/fixtures/wikidata/wikidata_nat_cohort_c_operator_evidence_packet_20260404.json`
- Ptolemy evidence fixture `tests/fixtures/wikidata/wikidata_nat_cohort_c_ptolemy_evidence_sample_20260405.json`
- The helper `build_nat_cohort_c_operator_index` in `src/ontology/wikidata_cohort_c_operator_index.py`

## Operator Guidance

- Run the helper after batch reporting to produce an index that maps reference anchors to all qualifier hints seen on nearby policy-risk candidates.
- Share the index alongside the batch report so reviewers can quickly scan where hold reasons concentrate and how qualifiers spread while a gate remains closed.
- No automation claims are made; rerun live preview if candidate populations shift before reusing the index.
- Operators can now run `sensiblaw wikidata cohort-c-operator-digest --inputs <packet1> <packet2> ...` to materialize a governance digest that aggregates hold reasons and reference qualifier penetration across indexes while keeping every row under `promotion_guard: hold`.
