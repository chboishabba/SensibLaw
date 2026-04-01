# Wikidata Review Packet Contract

Date: 2026-04-01

## Change Class

Standard change.

## Purpose

Define the first machine-readable contract for reviewer-facing Nat/Wikidata
split packets so the lane can attach bounded wiki-derived context to held
split-required rows without inventing a second authority model.

## Scope

This contract sits above:

- `sl.source_unit.v1`
- `sl.wikidata_split_plan.v0_1`

It is for:

- reviewer-facing packet assembly
- uncertainty reduction
- provenance-preserving review support

It is not for:

- direct migration execution
- direct semantic promotion from wiki prose
- open-ended crawling

## Contract Shape

Schema artifact:

- `SensibLaw/schemas/sl.wikidata_review_packet.v0_1.schema.yaml`

Runtime builder:

- `build_wikidata_review_packet(...)`

## Required packet sections

### 1. Source surface

- exact `source_unit_id`
- `entity_qid`
- revision id and timestamp
- page title and URL when present
- anchor refs showing the specific spans used for review

### 2. Split-review context

- one `split_plan_id`
- source slot id
- source candidate ids
- split status and suggested action
- merged split axes
- propagation expectations

### 3. Parsed page signals

- query links
- cited/outbound links
- unresolved questions
- expected qualifier properties
- expected reference properties

The first slice keeps parsing intentionally narrow and deterministic.

`parsed_page` is explicitly the shallow surface-parse layer, not the full
SensibLaw decomposition stack. It exists to capture bounded wiki-page
structure such as headings, task buckets, query rows, and cohort/task lines.
It does not yet claim clause-level decomposition, contingent-branch parsing,
semantic-unit extraction, or obligation-like reviewer logic.

Those richer SensibLaw capabilities should land as a later semantic layer
above or beside `parsed_page`, rather than being silently implied by the
current packet field.

### 4. Follow receipts

- zero or more bounded receipts
- each receipt records what was followed, why, what evidence was extracted, and
  what uncertainty remains

The first runtime slice now auto-derives a bounded receipt from the query-link
surface when one is present. Callers may still pass an explicit empty receipt
set to opt out, and packets remain empty when no bounded follow target exists.

An opt-in semantic sidecar now also exists behind
`include_semantic_decomposition=True`. It stays separate from `parsed_page`,
derives only from existing bounded packet signals, and is intentionally a
sidecar rather than a replacement for the shallow surface parse.

### 5. Reviewer view

- decision focus areas
- uncertainty flags
- recommended next step

## Governance

- packets are review aids, not authority transfer objects
- page text and followed links remain upstream evidence
- the optional semantic sidecar is still a review aid and not a hidden
  decomposition authority
- all packets must preserve the split plan as the execution-facing baseline
- unresolved uncertainty must stay visible
- shallow surface parse must not be misrepresented as full semantic
  decomposition

## Acceptance criteria

This slice is complete when:

1. a machine-readable schema exists
2. a runtime builder can attach one Nat wiki source unit to one held split plan
3. one pinned fixture validates against the schema
4. tests prove the packet preserves source revision, split-plan identity, and
   parsed qualifier/reference/query signals plus bounded follow-receipt
   behavior when a query-link surface exists

## ITIL / ISO / Six Sigma reading

- ITIL:
  standard change to the reviewer-assist service surface
- ISO 9000:
  packet quality is defined by bounded provenance and review usefulness
- ISO 42001:
  human review remains primary; packets reduce uncertainty rather than erase it
- ISO 27001:
  bounded receipts and revision locking reduce uncontrolled evidence spread
- Six Sigma:
  target defects are reviewer time loss, context-free split review, and hidden
  authority inflation

## C4 / PlantUML

```plantuml
@startuml
title Wikidata Review Packet Contract

Component(SOURCE, "SourceUnit", "Revision-locked wiki artifact")
Component(SPLIT, "SplitPlan", "Structured split baseline")
Component(PACKET, "ReviewPacket", "Reviewer-facing bounded packet")
Component(HUMAN, "Reviewer", "Nat / ontology group")

Rel(SOURCE, PACKET, "source surface + parsed signals")
Rel(SPLIT, PACKET, "split context")
Rel(PACKET, HUMAN, "review packet")

@enduml
```
