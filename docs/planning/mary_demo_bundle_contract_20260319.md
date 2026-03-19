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

AU/legal widening baseline:

- `source_label`: `wave1:real_au_procedural_v1`
- `workflow_kind`: `au_semantic`
- `workflow_run_id`: `run:5ab560b645ee10d0badd59fe6ef0a9442bf5d41bc57e7ff950688ae5961ef12d`

Current Mary completion stance:

- transcript `demo-bundle` remains the primary operator/demo baseline
- AU `demo-bundle` is the locked widening baseline for `SL-US-12` to `SL-US-14`
- future widening should follow the same `demo-bundle` seam rather than inventing new capture paths

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
