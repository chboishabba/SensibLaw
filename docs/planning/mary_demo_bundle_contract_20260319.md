# Mary Demo Bundle Contract

Date: 2026-03-19

## Purpose

Expose one stable persisted-run bundle for Mary-parity operator validation.

## Query seam

Use `scripts/query_fact_review.py demo-bundle`.

Preferred baseline today:

- `source_label`: `wave1:real_transcript_intake_v1`
- `workflow_kind`: `transcript_semantic`
- `workflow_run_id`: `transcript_acceptance_real_intake_v1`

Next widening target:

- `source_label`: `wave1:real_au_procedural_v1`
- `workflow_kind`: `au_semantic`

The bundle must include:
- `selector`
- `workbench`
- `acceptance`
- `sources`

## Resolution rules

- resolve run ids through the existing fact-review selector path
- prefer explicit selector args when provided
- otherwise project selector metadata from `reopen_navigation` / `run.workflow_link`

## Consumer rule

`itir-svelte` should test against captured `demo-bundle` output rather than re-deriving a second contract.
