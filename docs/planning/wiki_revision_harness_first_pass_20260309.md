# Wikipedia Revision Harness First Pass

Date: 2026-03-09
Status: active implementation note

## Intent
Add a first bounded live-revision harness around the existing Wikipedia timeline
and AAO extraction lane.

The first pass should let us:
- compare previous vs current Wikipedia revisions
- measure surface similarity and extraction-level drift
- summarize local graph-facing impact
- surface claim-bearing / attribution changes
- package reviewer-facing issue packets without implying an edit bot

This lane is not primarily about immediate GUI integration. The nearer goal is
to bring the wiki revision pipeline up to the same functional standard as other
active ITIR/SensibLaw pipelines:
- deterministic producer-owned artifacts
- dedicated state storage where appropriate
- explicit receipts and review context
- additive read models that other lanes can consume without re-deriving logic

The broader suite goal is collective uplift: when a pipeline reaches that
standard, other consumers and follow-on pipelines should be able to reuse its
artifacts, review posture, and provenance conventions instead of treating it as
an isolated harness.

## Chosen scope
- Use existing `wiki_pull_api.py` snapshots and `wiki_timeline_aoo_extract.py`
  payloads as inputs.
- Treat live fetching as normal, but make every report revision-explicit.
- Keep the output read-only and review-oriented.
- Allow missing extraction payloads and abstain explicitly instead of failing
  open.

## Deferred
- automatic edit suggestions
- direct Wikidata packet enrichment from live queries
- automatic truth adjudication or reasoner-driven narrative collapse
- scheduler/daemon behavior for rolling rechecks
- full `itir-svelte` workbench consumer

## Standardization target
The revision-monitor lane should converge with the newer suite patterns even if
it remains CLI-first for a while:
- queryable run/result state instead of blob-only inspection
- reusable producer-owned report/read-model surfaces
- shared provenance and receipt vocabulary where practical
- bridge-friendly outputs that other pipelines can consume read-only

UI integration is downstream of that standardization, not the driver for it.

## Contract link
- `docs/wiki_revision_harness_contract_v0_1.md`
- `docs/wiki_revision_pack_runner_contract_v0_1.md`
