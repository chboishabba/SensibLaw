# Wikipedia Revision Pack Runner Contract v0.1

## Purpose
Define the bounded rolling runner that executes the per-article Wikipedia
revision harness over a selected article pack.

This runner is:
- pack-scoped
- store-first
- read-only with respect to ontology rows
- CLI-first, with UI-ready persisted outputs

## Core stance
- The runner compares current article revisions against locally stored
  last-seen state.
- It does not depend on re-fetching arbitrary historical revisions from
  MediaWiki on every pass.
- The runner keeps its own dedicated SQLite state store.
- Review-context joins may attach curated and bounded auto-derived context, but
  they do not mutate bridge or ontology state.

## Pack manifest
Each pack manifest must include:
- `pack_id`
- `version`
- `scope`
- `provenance`
- `articles[]`

Each article entry must include:
- `article_id`
- `wiki`
- `title`
- `role` (`baseline` or `stress`)
- `topics[]`
- `review_context`

`review_context` is the curated primary context surface for the article. It may
include:
- QIDs
- diagnostic topics (`mixed_order`, `p279_scc`, `qualifier_drift`, `parthood`)
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

The state DB stores metadata and file references, not duplicated artifact blobs.

## Artifact layout
Default output root:
- `SensibLaw/demo/ingest/wiki_revision_monitor/<pack_id>/`

Per run, the runner may write:
- current snapshots
- timeline artifacts
- AAO artifacts
- per-article revision reports
- pack-level run summary export

These remain gitignored export artifacts.

## Runner behavior
For each article:
1. Fetch current snapshot.
2. Look up last-seen state in the dedicated SQLite store.
3. If no prior state exists:
   - store the current snapshot/artifact metadata as baseline
   - emit `baseline_initialized`
   - do not fabricate change packets
4. If `revid` is unchanged:
   - emit `unchanged`
   - do not rebuild comparison artifacts
5. If `revid` changed:
   - build current timeline + AAO artifacts
   - compare current vs last-seen artifacts through the revision harness
   - attach curated review context plus bounded auto-joined bridge context
   - persist run/result metadata
   - update last-seen state to the current artifacts

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
  - highest severity seen
  - top report paths / article ids

The persisted run/result model should be usable by a later `itir-svelte`
workbench without schema redesign.

## Current curated packs
Current curated manifests include:
- `SensibLaw/data/source_packs/wiki_revision_monitor_v1.json`
  - mixed baseline + ontology-stress pages
- `SensibLaw/data/source_packs/wiki_revision_contested_v1.json`
  - high-contestation pages across politics, ongoing conflict, religion, and
    politicized science/medicine
