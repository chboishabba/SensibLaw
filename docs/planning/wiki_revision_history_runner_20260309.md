# Wikipedia Revision History Runner (2026-03-09)

## Purpose
Move the bounded Wikipedia revision monitor beyond `last_seen -> current` into a
history-aware lane that can surface larger and more contested recent deltas.

## Main decision
Keep the existing store-first current monitor, but add bounded revision-history
polling per title and select only the top 1-3 candidate pairs for full report
generation.

## Required capabilities
- bounded revision-history polling per article
- deterministic candidate-pair scoring before full extraction
- pair kinds for:
  - `last_seen_current`
  - `previous_current`
  - `largest_delta_in_window`
  - `most_reverted_like_in_window`
- section-aware diff targeting for reviewer packets and triage

## Defaults
- `max_revisions = 20`
- `window_days = 14`
- `max_candidate_pairs = 3`
- `section_focus_limit = 5`

## Cross-project interface posture
- `SensibLaw` owns this lane as a source-ingest and comparison/report surface.
- `SL-reasoner` may consume pair reports as read-only hypothesis inputs only.
- `StatiBaker` may ingest observer-class refs to runs/pairs/issue packets only.
- `fuzzymodo` and `casey-git-clone` remain reference-only external consumers at
  this stage; they do not own pair selection, scoring, or article state.
