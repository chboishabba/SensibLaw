# Wiki Random General-Text Timeline Harness Contract v0.1

This harness is the **derived chronology/event readiness surface** for the
broader random-page article-ingest lane.

It exists to answer a different question from the parent article-ingest
contract:

- parent lane: can SL ingest broad arbitrary Wikipedia prose into bounded
  article-wide structure?
- this harness: can the canonical wiki-state compiler and existing adapters
  turn that same prose into reviewable, Mary-like chronology/event material?

## Goal

Treat random Wikipedia pages as a derived chronology stress surface for:

`snapshot -> canonical wiki state -> ordered timeline projection -> anchored chronology diagnostics`

This is relevant after the article-wide ingest surface is already in place:

- Mary-parity chronology expectations
- ITIR / TiRC general-text timeline work
- wider SL / SB event and story surfaces

## Pipeline

1. `scripts/wiki_random_page_samples.py`
   - live acquisition only
   - writes replayable revision-locked snapshot manifests

2. `src/wiki_timeline/article_state.py`
   - derives canonical article state with sentence/text units, observations,
     event candidates, and explicit anchor status

3. `scripts/report_wiki_random_timeline_readiness.py`
   - offline scoring only
   - scores whether a random-page sample yields ordered timeline-capable event
     surfaces plus anchored chronology diagnostics

## Ownership rule

This belongs to SensibLaw generally, not to an ITIR-only extension.

The timeline readiness report is a **Mary-parity diagnostic** over SL-owned
deterministic adapters. It does not create a second canonical event store and
it does not transfer semantic authority away from the existing SL contracts.

## Scored surface

The scored surface is **not** raw reducer output and it is **not** the whole
article-ingest score.

The scored surface is the deterministic adapter chain:

`canonical wiki state -> timeline projection -> anchored chronology diagnostics`

Expected page-level signals include:

- ordered event count
- explicit-anchor count
- weak-anchor count
- undated ordered-event count
- actor/action/object coverage over ordered events
- chronology support retention for the anchored subset

## Contract stance

- parser-first / deterministic extraction remains preferred
- article-wide ingest coverage is the parent deliverable; this harness is the
  chronology/event derivative
- the timeline view may include undated events, but anchor status must remain
  explicit so chronology quality is not overstated
- reducer coverage is a companion diagnostic, not the final deliverable
- chronology/event outputs remain observer signals, not normative truth
- this harness is offline-replay by default; live network is acquisition-only
- report outputs should stay replayable from stored manifests and snapshots

## Near-term follow-on

This harness broadens confidence that article-ingested general text can reach a
Mary-like timeline surface.

It does **not** replace the parent article-ingest contract, and it does
**not** yet replace the canonical fact-intake observation/event substrate. The
next bridge after this harness is:

`canonical wiki state / timeline projection -> canonical observation/event sender`
