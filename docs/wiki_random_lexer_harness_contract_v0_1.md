# Wiki Random Lexer Harness Contract v0.1

This harness is a read-only SensibLaw companion quality surface for broadening
canonical lexer/reducer coverage against Wikipedia random-page samples.

It is not the authoritative article-quality score for the random-page lane.
That parent role now belongs to the article-ingest contract:

- `SensibLaw/docs/wiki_random_article_ingest_coverage_contract_v0_1.md`

It is intentionally split into two tools:

1. `scripts/wiki_random_page_samples.py`
   - live acquisition only
   - fetches random Wikipedia titles
   - resolves them to revision-locked snapshots
   - writes a replayable manifest plus snapshot JSON under gitignored paths

2. `scripts/report_wiki_random_lexer_coverage.py`
   - offline scoring only
   - consumes stored manifests and snapshots
   - scores both:
     - raw tokenizer output as diagnostics
     - supported shared-reducer output as the scored cross-product surface

## Supported score families

- `structural_coverage_score`
  - how much of a page receives current reducer/tokenizer structural
    recognition
- `abstention_quality_score`
  - whether the current reducer/tokenizer posture stays clean and low-noise on
    pages where the present structure lane has little to say
- `shared_reducer_alignment_score`
  - whether tokenizer and shared-reducer surfaces agree on signal presence
- `overall_quality_score`
  - transparent composite over the three component scores

## Important ownership rule

This belongs to SensibLaw generally, not to an ITIR-only extension.

The canonical scored surface here is still the shared reducer contract in
`src/sensiblaw/interfaces/shared_reducer.py`, but this harness is now a
companion diagnostic to the broader article-ingest lane rather than the lane's
top-level success criterion. Raw tokenizer metrics remain diagnostics and audit
evidence, not the only public score surface.

## Explicit non-goal

Reducer or tokenizer signal by itself still does **not** constitute:

- fact summaries
- Mary-style chronology
- event candidates
- review-ready timeline rows

Those require the broader article-ingest and downstream chronology layers:

- `snapshot -> article sentences -> actor/action/object extraction`
- `snapshot -> timeline candidates -> AAO/general-text event extraction -> timeline readiness report`

See:

- `SensibLaw/docs/wiki_random_article_ingest_coverage_contract_v0_1.md`
- `SensibLaw/docs/wiki_random_general_text_timeline_harness_contract_v0_1.md`

## Operational rule

- live acquisition is never the default CI path
- offline replay/scoring is the default harness path
- tests must use stored sample snapshots and no live network
