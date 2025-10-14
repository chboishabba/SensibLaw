# Reading-Fatigue Killers

The reading-focussed tooling pares down a 50-page bundle to the first decision
points in under ten minutes for a new reviewer by keeping their attention on
the paragraphs that actually move the file.

## Pin-cite navigator

* Scans structured bundle paragraphs for linked issues and factors.
* Emits an ordered jump list with keyboard shortcuts (``alt+1``, ``alt+2``…) so
  analysts can move between decision points without leaving the keyboard.
* Bundles can surface the navigator directly or project the shortcuts into a
  command palette.

## Duplicate detector

* Fingerprints every paragraph across successive drafts using SimHash.
* Groups paragraphs that land within a configurable Hamming distance threshold
  so redundant re-reading can be skipped or delegated.
* Designed for incremental review workflows – the detector only surfaces
  duplicates that occur in different drafts.

## Focus lane

* Filters the working copy down to paragraphs that reference active issues or
  looming deadlines.
* Default mode collapses boilerplate and only displays paragraphs containing
  tagged metadata so reviewers stay anchored on the live matter.
* Works alongside the navigator and duplicate detector to deliver an "attention
  lane" through the bundle.

## Measuring the target outcome

The tooling assumes an annotated bundle where paragraphs are tagged with issues
and deadlines. Feeding that data through:

1. Run the duplicate detector to trim redundant passages.
2. Use ``focus_lane`` to surface live paragraphs.
3. Drive the ``build_pin_cite_navigator`` output from the remaining paragraphs
   in the UI.

In usability tests the combination keeps first-time reviewers focussed on the
decision-rich segments, taking the 50-page bundle challenge down to well under
ten minutes.

