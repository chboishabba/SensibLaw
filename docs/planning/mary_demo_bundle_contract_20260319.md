# Mary Demo Bundle Contract

Date: 2026-03-19

## Purpose

Expose one stable persisted-run bundle for Mary-parity operator validation.

## Query seam

Use `scripts/query_fact_review.py demo-bundle`.

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
