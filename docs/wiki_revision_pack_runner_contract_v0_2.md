# Wikipedia Revision Pack Runner Contract v0.2

Superseded in part by `docs/wiki_revision_pack_runner_contract_v0_3.md` for
the contested-region graph lane.

## Purpose
Define the bounded history-aware rolling runner that executes the per-article
Wikipedia revision harness over curated article packs.

This runner is:
- pack-scoped
- history-aware within bounded windows
- store-first for last-seen state
- read-only with respect to ontology rows
- CLI-first, with UI-ready persisted outputs

The current priority is functional parity with the rest of the suite's
stronger pipelines, not immediate GUI integration. In practice that means the
runner should keep converging toward the same standards now used elsewhere:
- deterministic producer-owned artifacts
- queryable run/result state
- additive read models over raw blobs
- explicit receipt/review-context surfaces
- bounded bridge/export posture for downstream consumers

## Core stance
- The runner still maintains current-vs-last-seen monitoring per article.
- It also polls a bounded recent revision window per article.
- Only the top selected candidate pairs get full extraction/report work.
- Review-context joins may attach curated and bounded auto-derived context, but
  they do not mutate bridge or ontology state.

## Pack manifest
Each pack manifest must include:
- `pack_id`
- `version`
- `scope`
- `provenance`
- `articles[]`

Optional pack-level defaults:
- `history_defaults.max_revisions`
- `history_defaults.window_days`
- `history_defaults.max_candidate_pairs`
- `history_defaults.section_focus_limit`

Each article entry must include:
- `article_id`
- `wiki`
- `title`
- `role` (`baseline` or `stress`)
- `topics[]`
- `review_context`

Optional per-article history overrides:
- `history.max_revisions`
- `history.window_days`
- `history.max_candidate_pairs`
- `history.section_focus_limit`

`review_context` is the curated primary context surface for the article. It may
include:
- QIDs
- diagnostic topics
- notes about why the article belongs in the pack

## State store
Default path:
- `SensibLaw/.cache_local/wiki_revision_harness.sqlite`

Minimum persisted surfaces:
- pack registry
- article registry
- current last-seen state per article
- run history
- article result rows per run
- revision-history rows per run/article
- candidate-pair rows per run/article

The state DB stores metadata and file references, not duplicated artifact blobs.

## Artifact layout
Default output root:
- `SensibLaw/demo/ingest/wiki_revision_monitor/<pack_id>/`

Per run, the runner may write:
- current snapshots
- history manifests
- selected-pair snapshots
- timeline artifacts
- AAO artifacts
- pair-level revision reports
- pack-level run summary export

These remain gitignored export artifacts.

## Runner behavior
For each article:
1. Fetch current snapshot.
2. Fetch bounded recent revision history.
3. Look up last-seen state in the dedicated SQLite store.
4. Materialize candidate pairs from:
   - `last_seen_current`
   - `previous_current`
   - `largest_delta_in_window`
   - `most_reverted_like_in_window`
5. Score candidate pairs before full extraction using metadata and lightweight
   section diffs.
6. Select only the top bounded candidate pairs for full timeline + AAO +
   harness comparison work.
7. Attach curated review context plus bounded auto-joined bridge context.
8. Persist run/result metadata and update the current last-seen state.

## Candidate scoring
Required score factors:
- byte-delta magnitude
- revert-like signal
- edit-frequency burst signal
- section-touch size

Scoring is deterministic and descriptive. It ranks candidate deltas; it does
not decide truth.

## Pair report envelope
The runner emits a pair-aware wrapper around the existing v0.1 revision harness
report.

Required pair-level fields:
- `pair_id`
- `pair_kind`
- `older_revision`
- `newer_revision`
- `candidate_score`
- `score_breakdown`
- `section_delta_summary`
- `comparison_report`

`comparison_report` remains the existing
`wiki_revision_harness_report_v0_1` payload.

## Review-context join model
Issue packets use a hybrid model:
- curated context from the pack manifest is primary
- auto-derived bridge context is secondary and explicitly labeled

Auto-derived context is bounded to:
- alias/bridge matches from the existing deterministic bridge slice
- known related entity surfaces extracted locally

Non-goals:
- open-ended entity resolution
- ontology mutation
- automatic Wikipedia/Wikidata edits

## Consumer surface
The first consumer is CLI-first.

The runner must emit:
- machine-readable JSON summary
- compact pack-level counts:
  - baseline initialized
  - unchanged
  - changed
  - error
  - candidate pairs considered
  - candidate pairs selected
  - pair reports built
  - highest severity seen
- pack-level triage summaries:
  - `pack_triage.top_changed_articles[]`
  - `pack_triage.top_high_severity_pairs[]`
  - `pack_triage.top_sections_changed[]`

Minimum `pack_triage` intent:
- `top_changed_articles[]` exposes article-level severity and primary selected
  pair metadata without reopening pair reports
- `top_high_severity_pairs[]` exposes the strongest pair-level deltas directly
- `top_sections_changed[]` exposes the most-touched sections across the pack so
  downstream consumers can triage by topic/section before loading per-pair
  artifacts

The persisted run/result model should be usable by a later `itir-svelte`
workbench without schema redesign, but GUI consumption is not the primary
success criterion for this stage. The primary success criterion is that this
lane reaches the same functional review/export/query standard as the rest of
the suite, so other pipelines can propagate and reuse its artifacts cleanly.

## Cross-pipeline posture
The revision-monitor lane should not stay a one-off harness.

Expected convergence points with other suite pipelines:
- producer-owned report/read-model contracts, not only raw JSON blobs
- consistent provenance and review-context labeling
- query-first access to latest runs, severities, and issue packets
- read-only bridgeability into adjacent lanes (`SL-reasoner`, `StatiBaker`,
  later workbenches) without those consumers re-deriving monitor logic

Non-goal for this contract revision:
- forcing the runner into GUI-first behavior before the functional/queryable
  producer standard is in place
