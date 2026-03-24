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

The current evaluation phase is no longer just “does the report run on a few
pages?” It is a generalization harness:

- rerun the random-page manifest on a larger slice
- compare regime distributions across pages
- surface dominant-regime counts and issue clustering
- track follow-yield separately from raw link relevance
- keep family labels as derived summary helpers only

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
- dominant-regime counts and regime-generalization summaries over larger slices

## Report posture

The article-ingest report now carries two parallel score families:

- legacy `scores`
  - coverage-oriented comparability surface
  - answers "did we extract bounded article structure at all?"
- `honesty_scores`
  - penalty-aware quality surface
  - answers "is the extracted structure bounded, clean, and plausibly bound to
    who-did-what relations?"

This keeps the older broad-coverage score visible while preventing noisy output
from looking artificially excellent.

## Required honesty diagnostics

The report contract should expose these additive scorer-only diagnostics:

- `observation_explosion_score`
  - penalize runaway observation density per sentence or per event candidate
- `text_hygiene_score`
  - penalize citation tails, template residue, smashed sentence joins, and
    similar malformed extracted text
- `actor_action_binding_score`
  - penalize events where an action exists but no actor is plausibly bound to
    it
- `object_binding_score`
  - penalize events where an action exists but no acted-on target/object is
    plausibly bound to it
- `article_ingest_honest_score`
  - derived from coverage score times an honesty multiplier over the above
    bounded penalties

The report should also expose density metrics such as observations per sentence,
observations per event, and step density so pressure-test runs can distinguish
real coverage from extraction blowup.

## Timeline honesty

Timeline quality remains a separate projection-level surface.

The article-ingest report should expose timeline honesty explicitly via:

- explicit anchor ratio
- weak anchor ratio
- none anchor ratio
- `timeline_honesty_score`

This chronology honesty surface must not directly reduce
`article_ingest_honest_score`. A page can ingest well while remaining mostly
undated.

## Calibration extension

After the initial honesty pass, the report should also expose a scorer-only
calibration layer so operators can distinguish real extraction weakness from
page-shape mismatch.

The calibration layer should include:

- `abstention_calibration_score`
  - reward conservative abstention on list-like, taxonomic, measurement-heavy,
    and otherwise structurally awkward sentences
  - penalize forced event extraction when the sentence looks more like
    structure/catalogue than article action
- `link_relevance_score`
  - measure whether sentence-local wiki links are actually participating in the
    extracted actor/object/attribution structure rather than merely surviving as
    unrelated decoration
- `claim_attribution_grounding_score`
  - measure whether claim-bearing and attribution-bearing rows remain text-
    grounded and minimally supported by actor/action/source structure

These should remain additive report surfaces. They may feed a calibrated score,
but they should not silently replace the earlier coverage or honesty tracks.

The report should also surface `follow_yield_metrics` so operators can
distinguish:

- relevant root links that survive extraction
- relevant one-hop follows that continue the same conceptual surface
- pages where link relevance is strong locally but weak after follow

The follow-yield score itself should be a 50/50 blend of:

- followed-link relevance
- follow-target quality for the continuation page itself

Follow-target quality should be a bounded blend of:

- richness
- non-list / non-disambiguation structure
- regime similarity
- information gain relative to the root page

The current graph-yield falsification phase should additionally expose:

- `follow_target_quality_score`
  - continuation quality for the followed page itself, not just overlap with
    the root page
- `two_hop_metrics`
  - hop-1 versus hop-2 quality decay for recursive one-hop-follow manifests
- `best_path_metrics`
  - the strongest observed continuation chain through the sampled follow tree,
    scored from hop-1 quality, hop-2 quality, and regime coherence
- `follow_failure_bucket_counts`
  - aggregated weak-follow buckets so operators can separate list-like,
    thin/stub, regime-jump, and low-information-gain failures
- `follow_failure_bucket_examples`
  - bounded concrete examples of those weak-follow buckets for manual review

The first live multi-hop campaign should be treated as a calibration datapoint,
not a victory lap. On the completed 8-page recursive run, the important
pattern was:

- root-link relevance stayed near-saturated
- followed-link relevance dropped sharply
- follow-target quality stayed materially below root relevance
- hop-2 quality did not collapse relative to hop-1 on that slice

Operators should therefore read the current bottleneck as:

- generic/list/aggregation continuation pages are still too admissible
- shallow path decay is not yet the dominant failure mode

The next tightening pass should focus first on:

- stronger non-list / generic-aggregation discrimination
- explicit failure bucketing over weak follow targets
- repeated-run distribution checks rather than one-off averages

## Page-family stratification

The random-page harness should now also emit a light page-family/profile guess
so different failure modes stop collapsing into one blended average.

Initial families should remain heuristic and bounded, for example:

- `biography`
- `place`
- `facility`
- `project_institution`
- `species_taxonomy`
- `general`

This page-family/profile surface is for summary stratification and operator
interpretation. It is not a classifier-training objective.

The summary surface should also remain family-aware when reporting averages and
issue pressure so a single biography or taxonomy page does not get normalized
against unrelated article shapes.

It should additionally report:

- dominant-regime counts
- average follow-yield metrics
- regime-aware summary averages for honesty and calibration

For repeated campaign analysis, summary/debug surfaces should make it easy to
separate:

- list/disambiguation/year-style aggregation follows
- thin/stub follows
- regime-jump follows
- low-information-gain follows

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
