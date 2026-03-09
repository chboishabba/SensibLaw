# Wikipedia Revision Pack Runner Contract v0.3

## Purpose
Extend the history-aware revision monitor into a bounded contested-region graph
lane over curated contested Wikipedia packs.

This contract adds:
- deeper curated contested history windows
- hybrid contested-region graph artifacts
- SQLite-backed contested graph read models
- pack-level contested graph triage
- a dedicated `itir-svelte` consumer page

It remains:
- read-only with respect to ontology rows
- bounded and curated, not a crawler
- reviewer-support and ingest-evaluation focused

## New pack surfaces
Additional manifest fields:
- pack-level `graph_enabled`
- article-level `graph_enabled`
- optional curated `review_context.contested_topics[]`

Current curated contested graph pack:
- `SensibLaw/data/source_packs/wiki_revision_contested_v2.json`

Default contested-pack v2 history posture:
- `max_revisions = 50`
- `window_days = 30`
- `max_candidate_pairs = 5`
- `section_focus_limit = 8`

## Contested-region graph artifact
`schema_version = wiki_contested_region_graph_v0_1`

Required sections:
- `article`
- `run`
- `regions[]`
- `selected_pairs[]`
- `events[]`
- `epistemic_surfaces[]`
- `edges[]`
- `cycles[]`
- `summary`

Cycle meaning in v1:
- a bounded revisitation pattern over the same section/semantic neighborhood
- not a contradiction proof
- not a truth-adjudication mechanism

Minimum edge kinds:
- `touches_region`
- `revises_after`
- `changes_event`
- `changes_attribution`
- `co_occurs_in_region`
- `escalates_region`
- `returns_to_region`

## State/read model additions
The dedicated revision-monitor SQLite store now also persists:
- `wiki_revision_monitor_contested_graphs`
- `wiki_revision_monitor_contested_regions`
- `wiki_revision_monitor_contested_cycles`
- `wiki_revision_monitor_contested_edges`

Heavyweight graph artifacts remain file exports under:
- `SensibLaw/demo/ingest/wiki_revision_monitor/<pack_id>/contested_graphs/`

## Run summary additions
Run summaries must now include:
- `contested_graph_counts`
- `pack_triage.top_contested_graphs[]`
- `pack_triage.top_contested_cycles[]`
- `pack_triage.top_contested_regions[]`

Article rows must now include:
- `contested_graph_available`
- `contested_graph_path`
- `contested_graph_summary`

## Consumer posture
First consumer page:
- `itir-svelte/src/routes/graphs/wiki-revision-contested/+page.svelte`

Cross-project posture remains unchanged:
- `SensibLaw` owns graph production
- `SL-reasoner` may consume read-only graph summaries
- `StatiBaker` may consume observer-only refs/summaries
- `fuzzymodo` and `casey-git-clone` remain reference-only external consumers

## Non-goals
- no automatic page discovery yet
- no broad crawl yet
- no ontology mutation
- no Wikipedia/Wikidata edit automation
- no contradiction/truth resolution from detected cycles
