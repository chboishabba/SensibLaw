# Wiki Random Lexer Harness Contract v0.1

This harness is a read-only SensibLaw quality surface for broadening canonical
lexer/reducer coverage against Wikipedia random-page samples.

It is the **stage-1 structural signal harness**, not the full Mary-parity
general-text timeline surface.

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
  - how much of a page receives legal/structural recognition
- `abstention_quality_score`
  - whether obviously non-legal pages remain cleanly abstained
- `shared_reducer_alignment_score`
  - whether tokenizer and shared-reducer surfaces agree on signal presence
- `overall_quality_score`
  - transparent composite over the three component scores

## Important ownership rule

This belongs to SensibLaw generally, not to an ITIR-only extension.

The canonical scored surface is the shared reducer contract in
`src/sensiblaw/interfaces/shared_reducer.py`.
Raw tokenizer metrics are included as diagnostics and audit evidence, not as
the only public score surface.

## Explicit non-goal

Reducer or tokenizer signal by itself does **not** constitute:

- fact summaries
- Mary-style chronology
- event candidates
- review-ready timeline rows

Those require the next deterministic layer:

`snapshot -> timeline candidates -> AAO/general-text event extraction -> timeline readiness report`

See:

- `SensibLaw/docs/wiki_random_general_text_timeline_harness_contract_v0_1.md`

## Operational rule

- live acquisition is never the default CI path
- offline replay/scoring is the default harness path
- tests must use stored sample snapshots and no live network
