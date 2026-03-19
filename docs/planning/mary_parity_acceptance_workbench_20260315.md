# Mary Parity Acceptance + Workbench

Date: 2026-03-15

## Purpose

Turn the Mary-parity fact substrate into a role-checkable operator surface.

The next parity bar is no longer only:

- canonical storage
- deterministic event assembly
- queryable review bundles

It is also:

- story-driven acceptance over persisted runs
- source-centric reopen paths
- bounded operator views
- one thin read-only workbench over the same contract

## Implemented contract

Backend/operator additions:

- story-driven acceptance report over a persisted fact-review run
- source-label listing for recent linked runs
- bounded operator views:
  - `intake_triage`
  - `chronology_prep`
  - `procedural_posture`
  - `contested_items`
- read-only `fact.review.workbench.v1` payload

Frontend/workbench addition:

- `itir-svelte` route `/graphs/fact-review`
- consumes persisted fact-review workbench payload + acceptance report
- remains read-only and provenance-first
- preferred consumer seam: `scripts/query_fact_review.py demo-bundle`
- canonical Mary transcript operator baseline:
  - `source_label`: `wave1:real_transcript_intake_v1`
  - `workflow_kind`: `transcript_semantic`
  - `workflow_run_id`: `transcript_acceptance_real_intake_v1`
- next widening target after transcript proof:
  - `source_label`: `wave1:real_au_procedural_v1`
  - `workflow_kind`: `au_semantic`
- operator surface requirements:
  - recent/source-centric reopen navigation
  - grouped issue filters for `missing_date`, `missing_actor`,
    `contradictory_chronology`, and `procedural_significance`
  - chronology separation for dated, approximate, undated, and no-event rows
  - clearer inspector distinction between party assertion, procedural outcome,
    and later annotation

## Acceptance stance

- wave 1 legal operators remain the first gating pressure
- wave 1 should now be exercised through a canonical fixture manifest plus a
  batch acceptance runner over transcript/AU-backed persisted runs
- Mary UI proof should map directly to wave-1 story expectations:
  - `SL-US-09` intake triage / chronology split / inspector distinction
  - `SL-US-10` source-centric reopen path
  - `SL-US-11` assertion vs later annotation visibility
  - `SL-US-12` to `SL-US-14` procedural posture visibility
- balanced SL + ITIR and trauma/advocacy lanes remain follow-on pressure
- synthetic + real mix is acceptable for this phase, but real persisted runs
  should remain the preferred benchmark where available

## Design rule

The workbench is a consumer of the persisted fact-review run.

It must not:

- invent a second backend
- re-derive chronology/review logic in the UI
- mutate or adjudicate the stored substrate
