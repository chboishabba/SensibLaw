# Wikipedia Revision Harness Contract v0.1

## Purpose
Define a bounded, read-only harness for comparing Wikipedia article revisions as
live ingest/evaluation inputs for SensibLaw/ITIR and as reviewer-support inputs
for Wikipedia/Wikidata-adjacent work.

This harness is not an edit bot, not an ontology upsert path, and not an
authority transfer mechanism. It compares article revisions, reports local
extraction/graph effects, and packages issue packets for human review.

## Core stance
- Wikipedia article revisions are source artifacts.
- Live volatility is treated as signal, not as a failure by itself.
- Each run must still record explicit revision metadata so the observed delta is
  attributable and replayable when the revisions remain available.
- Wikidata remains downstream advisory context only; it does not define article
  truth or mutate canonical ontology rows.

## Inputs
- Previous revision source artifact:
  - `wiki`
  - `title`
  - `revid`
  - `rev_timestamp`
  - `source_url`
  - `fetched_at`
  - `wikitext` or equivalent article text
- Current revision source artifact:
  - same fields as above
- Optional previous/current AAO extraction payloads from
  `scripts/wiki_timeline_aoo_extract.py`
- Optional bounded review context attached by local tooling

## Output report
`schema_version = wiki_revision_harness_report_v0_1`

Required top-level sections:
- `article`
- `revisions`
- `similarities`
- `extraction_delta_summary`
- `graph_impact_summary`
- `epistemic_delta_summary`
- `issue_packets[]`
- `triage_dashboard`

### `article`
- Identifies the compared article:
  - `wiki`
  - `title`
  - `source_url`

### `revisions`
- Carries previous/current revision metadata:
  - `revid`
  - `rev_timestamp`
  - `fetched_at`
  - `available`
- Includes `same_article` to fail closed on accidental cross-article compares.

### `similarities`
- Separates raw article-surface similarity from extraction-surface similarity.
- Minimum required metrics:
  - normalized text lengths
  - token Jaccard similarity
  - SimHash fingerprints
  - SimHash Hamming distance
- Similarity metrics are descriptive only; they do not decide truth.

### `extraction_delta_summary`
- Summarizes local extractor-visible changes:
  - event counts
  - changed/added/removed `event_id`s
  - unique actor/action/object deltas
- If extraction payloads are missing, emit explicit abstention fields rather
  than pretending the delta is empty.

### `graph_impact_summary`
- Reports the local graph-facing effect of the revision delta:
  - added/removed actor surfaces
  - added/removed action labels
  - added/removed object surfaces
  - whether the local extracted graph changed materially
- This remains a local impact summary, not a claim that the outside world
  changed.

### `epistemic_delta_summary`
- Tracks claim-bearing and attribution-sensitive changes:
  - claim-bearing event counts
  - changed/added/removed claim-bearing `event_id`s
  - attribution count deltas
  - event ids with attribution changes
- Conflict adjudication is out of scope; the harness only surfaces the change.

### `issue_packets[]`
- Reviewer-facing bounded packets for changed revision surfaces.
- Required fields:
  - `packet_id`
  - `event_id`
  - `severity`
  - `surfaces[]`
  - `summary`
  - `previous_event_present`
  - `current_event_present`
  - `related_entities[]`
- `surfaces[]` are drawn from:
  - `narrative`
  - `semantic`
  - `logical`
  - `epistemic`

### `triage_dashboard`
- Compact ranking surface over `issue_packets[]`.
- Required fields:
  - `packet_counts`
  - `top_packet_ids`
  - `highest_severity`
  - `material_graph_change`

## Non-goals
- No automatic Wikipedia edits.
- No automatic Wikidata edits.
- No automatic ontology mutation.
- No LLM-required truth adjudication.
- No silent collapse of article drift into one canonical story.

## Current implementation boundary
v0.1 is a harness and reporting slice:
- revision metadata capture
- similarity reporting
- extraction delta summary
- local graph-impact summary
- claim-bearing / attribution delta summary
- bounded issue packets + triage dashboard

Possible future layers:
- richer review-context joins to bounded Wikidata diagnostics
- downstream handoff artifacts for SL-reasoner or LLM analysis
- curated edit-suggestion lanes kept clearly advisory

Current pack-runner companion contract:
- `docs/wiki_revision_pack_runner_contract_v0_1.md`
