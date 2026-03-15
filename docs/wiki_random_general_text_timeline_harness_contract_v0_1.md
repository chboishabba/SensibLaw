# Wiki Random General-Text Timeline Harness Contract v0.1

This harness is the **stage-2 Mary-parity readiness surface** for broad
general text.

It exists to answer a different question from the lexer/reducer harness:

- stage 1: can canonical SL structure surfaces see bounded signal in arbitrary
  Wikipedia prose?
- stage 2: can the existing deterministic timeline/AAO adapters turn that same
  prose into reviewable, Mary-like chronology/event material?

## Goal

Treat random Wikipedia pages as a broad general-text stress surface for:

`snapshot -> timeline candidates -> AAO events -> timeline readiness scoring`

This is relevant to:

- Mary-parity chronology expectations
- ITIR / TiRC general-text timeline work
- wider SL / SB event and story surfaces

## Pipeline

1. `scripts/wiki_random_page_samples.py`
   - live acquisition only
   - writes replayable revision-locked snapshot manifests

2. `scripts/wiki_timeline_extract.py`
   - derives bounded date-anchored timeline candidate rows from snapshot prose

3. `scripts/wiki_timeline_aoo_extract.py`
   - derives sentence-local AAO mini-graphs over those candidates
   - remains non-causal, non-authoritative, and provenance-preserving

4. `scripts/report_wiki_random_timeline_readiness.py`
   - offline scoring only
   - scores whether a random-page sample yields timeline-capable event surfaces

## Ownership rule

This belongs to SensibLaw generally, not to an ITIR-only extension.

The timeline readiness report is a **Mary-parity diagnostic** over SL-owned
deterministic adapters. It does not create a second canonical event store and
it does not transfer semantic authority away from the existing SL contracts.

## Scored surface

The scored surface is **not** raw reducer output.

The scored surface is the deterministic adapter chain:

`wiki_timeline_extract -> wiki_timeline_aoo_extract`

Expected page-level signals include:

- timeline candidate count
- dated candidate count
- AAO event count
- actor/action/object coverage over derived AAO events
- chronology support retention from timeline candidates into AAO events

## Contract stance

- parser-first / deterministic extraction remains preferred
- reducer coverage is a prerequisite diagnostic, not the final deliverable
- chronology/event outputs remain observer signals, not normative truth
- this harness is offline-replay by default; live network is acquisition-only
- report outputs should stay replayable from stored manifests and snapshots

## Near-term follow-on

This harness broadens confidence that general text can reach a Mary-like
timeline surface.

It does **not** yet replace the canonical fact-intake observation/event
substrate. The next bridge after this harness is:

`general text timeline/AAO output -> canonical observation/event sender`
