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

Historical backcompat boundary in v0.3:

- `summary_json` and `graph_json` were the bounded fallback/export surfaces at
  that point in the contraction sequence
- article-result and candidate-pair operational blob columns were already no
  longer canonical and existed only as temporary compatibility residue
- the explicit contraction plan was tracked in:
  - `../docs/planning/wiki_revision_monitor_blob_deprecation_matrix_20260331.md`
  - `../docs/planning/wiki_revision_monitor_schema_contraction_plan_20260331.md`
  - `../docs/planning/wiki_revision_monitor_v0_4_placeholder_blob_drop_20260331.md`

Current state beyond this v0.3 note:

- later v0.4/v0.5 contraction slices removed the legacy blob columns from both
  fresh schema creation and old-DB migration
- the query lane is now SQLite-first and no longer uses DB blob fallback
- routine pair-report/contested-graph JSON report artifacts are no longer the
  intended default report surface
- local path fields are no longer the intended semantic identity surface;
  truth remains in SQLite/read models, while any surviving local paths are
  provenance-only or transitional implementation residue unless a concrete
  downstream consumer requires them
- the later path-residue cut removed `timeline_path` and `aoo_path` from
  article-state and article-result storage entirely; only bounded
  provenance-only residue such as `snapshot_path` and transitional `out_dir`
  remains
- hosted/shareable provenance should resolve through logical artifact identity,
  revision, digest, sink refs, and acknowledgements rather than local JSON
  files or local filesystem paths alone

The current default runner posture beyond this v0.3 contract note is:
- no routine pair-report JSON report artifacts
- no routine contested-graph JSON report artifacts
- SQLite/read models remain the canonical operational surface

## Run summary additions
Run summaries must now include:
- `contested_graph_counts`
- `pack_triage.top_contested_graphs[]`
- `pack_triage.top_contested_cycles[]`
- `pack_triage.top_contested_regions[]`

Article rows must now include:
- `contested_graph_available`
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
