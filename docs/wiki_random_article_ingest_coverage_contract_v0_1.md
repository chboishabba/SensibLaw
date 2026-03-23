# Wiki Random Article-Ingest Coverage Contract v0.1

This contract defines the primary SensibLaw quality surface for arbitrary
revision-locked Wikipedia pages.

It supersedes the earlier framing where random-page work was treated mainly as
timeline readiness over date-anchored candidates. The primary question is now:

`how much of a page can SL ingest into bounded, reviewable structure?`

Timeline quality remains important, but as a derived surface.

## Goal

Treat random Wikipedia pages as a broad article-ingest stress surface for:

`snapshot -> canonical wiki state -> article ingest projection -> derived timeline projection -> bounded one-hop follow`

This lane is relevant to:

- general SL article-ingest quality
- Mary-parity pressure on chronology-enabling content
- ITIR/TiRC article-to-structure workflows over non-legal text

## Canonical stance

This lane now treats Wikipedia ingest as one deterministic compiler plus
multiple projections:

`revision-locked article -> canonical wiki state -> article ingest / timeline / revision views`

The canonical middle is article-wide and date-agnostic by default. It should
reuse the existing SL fact-intake vocabulary where possible:

- sentence/text units
- normalized observation-style rows
- conservative `EventCandidate`s
- claim-bearing and attribution-bearing units
- anchor candidates with explicit strength/status

Timeline rows are not the canonical ingest ontology. They are one view over the
same state.

## Current v0.1 path

- `scripts/wiki_random_page_samples.py`
  - live acquisition only
  - writes replayable revision-locked root snapshots
  - may attach bounded one-hop followed snapshots with explicit caps
- `src/wiki_timeline/article_state.py`
  - canonical deterministic compiler for article-wide wiki state bundles
- `scripts/report_wiki_random_article_ingest_coverage.py`
  - offline scoring only
  - scores canonical article-ingest coverage plus derived timeline/reducer
    companion surfaces

## Primary scored surface

The primary scored surface is canonical article ingestion, not only
date-anchored rows.

Expected page-level signals include:

- sentence/text-unit count
- observation/event-candidate retention
- actor/entity surface coverage
- action surface coverage
- object/context surface coverage
- claim/attribution visibility
- unresolved/abstained coverage
- bounded timeline visibility with explicit anchor status (`explicit`, `weak`,
  `none`)
- bounded one-hop follow yield from extracted wiki links

## Extraction stance

- prefer deterministic sentence-local extraction over speculative synthesis
- identify the people/entities named in the article and what they did
- carry when/where/why/context only when text-local deterministic extraction
  supports it
- keep actor/entity coalescing conservative and deterministic
- do not require legal framing for arbitrary non-legal pages
- keep ordering explicit even when no date is available; undated extracted
  events still belong in the timeline projection with `anchor_status = none`
- keep legal-specific reducer scoring as an optional comparison slice, not the
  main success condition for this lane

## One-hop follow posture

- live acquisition remains separate from offline scoring
- first-hop following is allowed with explicit caps
- no deeper crawl in v0.1
- followed pages must remain revision-locked and replayable from stored
  manifests/snapshots
- one-hop follow is additive context only; it does not silently rewrite the
  source page's extracted truth surface
- followed-page extraction must preserve provenance back to the root article and
  remain a separate additive context surface

## Companion surfaces

The older random-page harnesses remain valid, but as subordinate surfaces:

- `SensibLaw/docs/wiki_random_lexer_harness_contract_v0_1.md`
  - reducer/tokenizer companion diagnostics
- `SensibLaw/docs/wiki_random_general_text_timeline_harness_contract_v0_1.md`
  - derived chronology/event readiness over the same page family
- `SensibLaw/docs/wiki_revision_harness_contract_v0_1.md`
  - revision/state-delta review over the same canonical wiki-state seam

## Operational rule

- live network is acquisition-only
- offline replay/scoring is the default harness path
- tests must use stored sample snapshots and no live network

## Near-term follow-on

After this v0.1 article-ingest lane is stable:

- deepen shared-reducer non-legal baseline diagnostics
- pressure-test more arbitrary page families
- tighten the bridge from canonical wiki-state observations/event candidates
  into the broader fact-intake sender/receiver chain
- keep one-hop follow bounded and replayable rather than widening into a
  crawler
