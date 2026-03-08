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

## Contract link
- `docs/wiki_revision_harness_contract_v0_1.md`
- `docs/wiki_revision_pack_runner_contract_v0_1.md`
