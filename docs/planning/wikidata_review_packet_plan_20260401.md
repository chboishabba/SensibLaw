# Wikidata Review Packet Plan

Date: 2026-04-01

## Change Class

Standard change.

## Purpose

Pin the exact next implementation plan for the user-story-backed wiki
review/split assist lane before any new code is written.

The goal is not to create a freeform scraper or hidden authority path. The
goal is to produce bounded reviewer packets that reduce uncertainty for
split-heavy Nat/Wikidata review.

When the work surface is wide enough to justify parallelism, the orchestration
rule is one nonblocking lane per worker, with disjoint lane ownership and no
shared write surface unless a later checkpoint explicitly merges it.

## Current State

What already exists:

- revision-locked wiki proposal capture
- migration-pack and split-plan generation
- checked-safe verification for bounded direct migrations
- runtime split verification for expected after-state on reviewed split plans

What is still missing:

- broader packet coverage across held Nat rows
- later semantic decomposition above or beside `parsed_page`
- a bounded variant-comparison lane for targeted uncertainty reduction

Update:

- the machine-readable contract layer is now pinned at
  `SensibLaw/docs/planning/wikidata_review_packet_contract_20260401.md`
- the first bounded runtime slice now exists:
  - `SensibLaw/schemas/sl.wikidata_review_packet.v0_1.schema.yaml`
  - `build_wikidata_review_packet(...)`
  - `SensibLaw/tests/fixtures/wikidata/wikidata_nat_review_packet_20260401.json`
- the bounded parser upgrade is now landed:
  - section headings
  - done / to-do task buckets
  - explicit query rows
  - explicit cohort/task lines
- the bounded follow-receipt seam now also exists for selected query-link
  surfaces, with explicit empty receipts still allowed as an opt-out
- important explicit boundary:
  - the current `parsed_page` field is only a shallow surface parse
  - it is not the full SensibLaw decomposition or contingent-clause layer
  - richer semantic decomposition should land later as a separate semantic
    layer above or beside `parsed_page`
- the first broader packet-coverage surface is now present at `15 / 53`
  packetized rows, spanning the original two held rows plus the AstraZeneca
  held row, the wider-online reviewed rows from the live tranche, two
  additional wider-online reviewed rows (`Q1785637`, `Q738421`), and two
  additional pilot-pack split plans (`Q10416948`, `Q56404383`) that now carry
  the semantic sidecar
- the current packet coverage surface is now `15 / 53` after the two
  additional live-tranche rows and the two pilot-pack sidecar packets were
  added
- the optional semantic sidecar is now landed behind
  `include_semantic_decomposition=True` and stays separate from
  `parsed_page`
- the semantic sidecar now explicitly records anchor-derived reviewer units
  and split-review context units (merged split axes + recommended action)
  so reviewers can reach the same conclusion without assuming the parsed
  surface is semantic decomposition
- the same semantic sidecar now also lifts bounded follow receipts into
  candidate units when they are present, so the receipt boundary stays visible
  without being overstated as grounded semantic promotion
- the same sidecar also promotes its `missing_evidence` list into explicit gap
  units so the reviewer can see what still is not grounded yet
- the next implementation pressure is broader packet coverage across the
  remaining held Nat rows, then any later expansion of the semantic sidecar
  above or beside `parsed_page`
- from this point onward the packet coverage lane is experiencing diminishing
  returns; only genuinely new split shapes should trigger another packet
  attachment rather than repeated routine rows.
- the helper-lane slices now exist as standalone modules and are aggregated
  behind the optional semantic sidecar:
  - follow depth
  - claim-boundary mapping
  - cross-source alignment
  - reviewer actions
  - bounded variant comparison
  - the remaining work is to extend their evidence inputs, not to widen the
    packet contract
- variant comparison now has a grounded Nat example path: when the split
  payload includes sibling plans from the same cohort, the packet can derive
  a small bounded comparison set automatically, so the comparison lane is no
  longer limited to abstract examples

## Planned Workflow

### Step 1: Capture

Capture the relevant wiki surface as a revision-locked artifact:

- page title / page id
- revision id
- timestamp
- URL
- raw text
- section anchors

### Step 2: Parse

Parse only the useful review structure. This is intentionally a shallow
surface parse, not full SensibLaw semantic decomposition:

- headings
- task lists
- query links
- cited references
- outbound links
- explicit qualifier/reference expectations
- explicit unresolved questions

Do not overclaim this layer. Clause-level decomposition, contingent branches,
semantic-unit extraction, and richer reviewer-logic surfaces belong to a later
semantic layer, not to the current `parsed_page` helper field.

### Step 3: Follow

Follow only selected links that are likely to reduce uncertainty:

- cited reports
- proposal/discussion pages
- methodology pages
- source documents already referenced by the page

Every followed source must produce a receipt:

- what was followed
- why it was followed
- what evidence was extracted
- what uncertainty remains

### Step 3b: Compare variants

Compare only a small bounded set of relevant variants when the comparison is
likely to reduce reviewer uncertainty:

- adjacent statement bundles in the same cohort
- nearby wiki revisions of the same proposal/sandbox page
- alternate query/result slices for the same target shape
- source/reference variants that explain why one row splits differently from
  another

Variant comparison is a diagnostic lever, not a truth engine. It should help
cluster split shapes and sharpen reviewer packets, but it must not become
open-ended diff-hunting or a substitute for the review packet itself.

### Step 4: Packetize

Attach the parsed page plus followed-source receipts to the existing review
lane for split-required cases.

If multiple disjoint review cohorts are active, packetize them in parallel
across separate workers rather than serializing every lane through one runner.
Only do this when the lane split is genuinely disjoint and review-safe.

The reviewer packet should show:

- the relevant Wikidata statement bundle
- the exact wiki revision/span that motivated review
- cited references and followed-source receipts
- the proposed split shape
- unresolved questions
- reviewer decision points

### Step 5: Preserve Governance

Nothing in the packet directly executes edits just because it was found.

Promotion still requires the existing bounded checks:

- provenance preserved
- qualifiers preserved
- references preserved
- expected after-state verified
- reviewer acceptance where needed

## ZKP Frame

### O

- Nat and related Wikidata working-group reviewers
- ITIR as capture/packetization substrate
- SensibLaw as migration/review runtime

### R

- reduce reviewer effort and uncertainty for split-heavy rows
- keep the product review-first and fail-closed

### C

- wiki revision capture surfaces
- split-plan and split-verification surfaces
- next reviewer-packet contract and parser/follow seams

### S

- doctrine and user-story backing are now explicit
- the next slice is specified but not implemented

### L

1. revision captured
2. page parsed
3. refs/links exposed
4. selected sources followed with receipts
5. targeted variants compared where useful
6. reviewer packet emitted
7. reviewer decides

### P

- build reviewer-packet infrastructure above the existing split-plan lane
- keep variant comparison bounded and diagnostic, not authoritative

### G

- no hidden authority promotion
- no autonomous edit execution from followed pages
- unresolved uncertainty remains explicit

### F

- the gap is now implementation, not intent

## ITIL Reading

- service: reviewer-assist packet generation for split-heavy Wikidata migration
  work
- change type: standard planning/governance clarification
- next standard changes:
  - packet contract
  - bounded parser
  - broader packet coverage across held rows, now with an 11-row surface
  - optional semantic decomposition sidecar above or beside `parsed_page`
  - bounded variant-comparison lane for targeted uncertainty reduction

## ISO 9000 Reading

Quality objective:

- give reviewers the best bounded evidence packet available without widening
  authority claims

Quality controls:

- revision locking
- explicit parser outputs
- explicit follow receipts
- explicit unresolved questions

## ISO 42001 Reading

- human review remains primary
- evidence augmentation does not become silent machine truth
- uncertainty reduction is allowed; uncertainty erasure is not

## ISO 27001 Reading

- bounded follow behavior reduces uncontrolled source sprawl
- receipts preserve what was inspected and why
- revision locking reduces ambiguity about the inspected source state

## Six Sigma Reading

Primary defect classes to reduce:

- reviewer time lost to repeated manual source chasing
- split-review ambiguity from context-free rows
- hidden authority inflation from followed links
- inconsistent provenance across reviewer decisions

## C4 View

### Context

- Wiki pages are upstream proposal/evidence surfaces
- ITIR captures and structures them
- SensibLaw turns them into split/review packets
- reviewers decide

### Container

- revision capture layer
- shallow wiki surface-parse layer
- later semantic decomposition layer
- bounded link-follow receipt layer
- split-plan / verification layer
- reviewer packet layer

## PlantUML

```plantuml
@startuml
title Wikidata Review Packet Plan

Component(WIKI, "Wiki Revision", "Revision-locked page / sandbox")
Component(PARSE, "Parser", "Sections, refs, links, tasks")
Component(FOLLOW, "Bounded Follow", "Selected source receipts")
Component(SPLIT, "Split Review Runtime", "Split plans + verification")
Component(PACKET, "Reviewer Packet", "Decision-focused review bundle")
Component(HUMAN, "Reviewer", "Nat / working-group reviewer")

Rel(WIKI, PARSE, "capture")
Rel(PARSE, FOLLOW, "selected refs/links")
Rel(PARSE, SPLIT, "constraints")
Rel(FOLLOW, PACKET, "receipts")
Rel(SPLIT, PACKET, "split context")
Rel(PACKET, HUMAN, "review packet")
@enduml
```

## Immediate Next Slice

Implement in this order:

1. broader packet coverage across the remaining held Nat rows
2. bounded variant-comparison lane for targeted uncertainty reduction
3. optional semantic decomposition layer above or beside `parsed_page`

## This Pass

This plan now serves as the workflow reference for the reviewer-packet lane.

The implementation has since begun and the current lane state now includes:

- the contract
- the shallow parser
- bounded follow receipts
- an 11-row Nat attachment surface

The remaining work is the broader packet coverage across held Nat rows and
any later expansion of the semantic sidecar above or beside `parsed_page`.
The new bounded variant-comparison lane now sits between those two stages so
reviewers can compare a few relevant variants without turning the packet into
an open-ended diff hunt.
