# Wikipedia Contested Region Graph Lane (2026-03-09)

## Intent
Turn repeated contested Wikipedia section churn into a bounded graph/read-model
 that can support both ingest diagnostics and reviewer triage.

## Current slice
- curated contested pack expansion:
  - `wiki_revision_contested_v2`
- deeper bounded history windows
- hybrid contested-region graph artifacts built from:
  - selected revision pairs
  - section delta summaries
  - extraction delta summaries
  - epistemic / attribution delta summaries
- SQLite read model + JSON export artifacts
- dedicated `itir-svelte` page for triage

## Graph semantics
- a contested region is a local article neighborhood, primarily section-shaped
  in v1
- a cycle means repeated return to the same contested region across selected
  pair deltas
- these cycles are review artifacts, not truth claims or ontology edits

## Deliberate bounds
- curated packs only
- no open-ended mining/crawl in this slice
- no contradiction adjudication
- no automatic suggestion/edit bot behavior

## Deferred follow-ons
- top-contested mining mode (stub/contract only)
- broad crawl mode (stub/contract only)
- richer graph visualization beyond the first dedicated page
