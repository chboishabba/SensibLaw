# Wikidata Nat End Product And Tiered Automation

Date: 2026-04-01

## Purpose

State the full intended end product for Nat's `P5991 -> P14143` lane in plain
operational terms, and make explicit that full pipeline coverage is the real
goal. The long-term P0 moonshot is a blind migration bot, but the current lane
is the review-and-split workbench that has to earn that level of automation.

Use
`SensibLaw/docs/planning/wikidata_nat_gap_to_moonshot_program_20260402.md`
for the explicit staged gap, promotion gates, and roadmap from the current
review-first posture to that moonshot.

## Plain-Language End Product

The destination is a review-and-split workbench for Nat and related Wikidata
reviewers.

It should let reviewers:

- start from a revision-locked wiki proposal or sandbox page
- see explicit statement cohorts instead of one undifferentiated backlog
- inspect held or split-required rows through compact reviewer packets
- receive proposed split shapes plus preserved qualifier/reference context
- move genuinely simple rows through checked-safe export and verification
- keep unresolved or policy-heavy rows visible instead of forcing them through

The product is therefore:

- not a blind migration bot yet
- not a vague queue of hard rows
- but a governed backlog-processing system with different lanes for different
  levels of certainty

The blind migration bot is the P0 moonshot for the lane, but it sits on top of
the review-and-split workbench rather than replacing it.

Operationally, that also means Nat can be run with multiple disjoint review
lanes at once when the surface is wide enough: one nonblocking lane per worker
is preferable to a single serialized pass, as long as the lanes stay disjoint
and review-first.

## Full Intended Flow

1. Capture the relevant wiki/discussion/proposal surface as a revision-locked
   artifact.
2. Build or refresh the relevant Wikidata candidate cohort/tranche.
3. Classify each row as checked-safe, split-required, review-only, held, or
   abstain.
4. For split-heavy cases, attach a bounded reviewer packet:
   - relevant wiki spans
   - qualifiers/references already present
   - cited references
   - selected followed-source receipts
   - proposed split shape
   - unresolved questions
5. Let the reviewer decide rather than re-research from scratch.
6. Export only genuinely checked-safe rows for bounded execution.
7. Verify the resulting after-state for promoted rows or reviewed split plans.
8. Keep provenance and uncertainty visible throughout.

## Tiered Automation Posture

The honest end state is tiered, not uniform.

## April 21 Family-To-Tier Mapping

The April 12 routing update adds an action taxonomy over the older Nat source
cohorts. The Nat cohorts still describe where rows came from. The families
below describe what the system should do with an inspected row.

- Family A: clean model-aligned rows map to Tier 1 / `full_auto`.
- Family B: structured rows that need decomposition map to Tier 2 /
  `split_auto`.
- Family C: model-incomplete rows map to repair plus migrate review before any
  promotion.
- Family D: valid subjects with weaker typing map to Tier 3 or Tier 4
  review-only typed hold.
- Family E: broken or legacy mixed rows map to manual reconstruction, not
  automation.

The property boundary is conservative:

- annual organization-level emissions can route to `P14143`
- product or lifecycle carbon footprint should stay on `P5991`
- emissions intensity should be held, not forced into `P14143`
- avoided emissions, offsets, and removals should be held until a specific
  target property is confirmed
- non-emissions metrics are blocked

This means broad automation readiness is measured by stable Family A evidence,
not by Nat Cohort A population size.

### Tier 1: Fully Automated

Use for rows that repeatedly prove safe under the same checks:

- stable semantic shape
- expected qualifiers
- expected references
- successful after-state verification

### Tier 2: Semi-Automated Split

Use for rows where the system can propose the split and present enough evidence
for rapid human approval.

### Tier 3: Review-Only Packet

Use for rows where ITIR reduces uncertainty and assembles the best evidence
packet, but the reviewer still decides structure and action.

### Tier 4: Hold

Use for rows that remain too ambiguous, policy-heavy, or weakly evidenced to
promote or split safely.

## Current Honest State

### What is complete

- Nat bounded mainline is complete.
- The wider proof lane is complete.
- The wider online lane has already shown that broader Cohort A passes are
  review-first rather than direct-safe by default.
- Split-plan-first review and split verification are now real bounded surfaces.

### What is not complete

- The wider online lane is not yet a broad direct execution lane.
- The reviewer-packet lane is real, but its remaining leverage is grounding
  depth and non-company structural breadth rather than more packet shape.
- Cohorts B, C, D, and E remain review-first branches rather than promoted
  automation families.
- the automation-graduation ceiling remains at Level 1, not yet at broad
  family-scoped automation.
- several moonshot-gap branches now have reproducible operator/report surfaces
  and CLIs, but those improve auditability and repeatability rather than
  changing the current automation tier by themselves.
- those same branches now also have broader operator/governance indexes over
  repeated batches or evidence snapshots, but those still improve control and
  auditability rather than changing the automation tier by themselves.

## ZKP Frame

### O

- Nat and related Wikidata editors
- ITIR as packetization/review-assist substrate
- SensibLaw as migration, split, and verification runtime

### R

- process the full backlog with bounded governance and reviewer speed, not with
  false uniform automation

### C

- migration packs
- split plans
- split verification
- next reviewer-packet lane
- grounding-depth, cohort-review, and graduation operator/report surfaces

### S

- direct-safe execution exists for a tiny bounded subset
- wider scale pressure is predominantly split/review
- next product value is better packetization, not pretending everything is Tier
  1

### L

1. checked-safe execution
2. semi-automated split
3. review-only packet
4. hold

### P

- design for full pipeline coverage across all rows, while only automating the
  rows that repeatedly justify it
- treat the blind migration bot as the P0 moonshot after the review/split
  workbench proves the safe lanes are stable enough to automate further

### G

- full backlog coverage is allowed
- blind full-population execution is not the target
- blind migration bot automation is the moonshot, not the current default

### F

- the main missing pieces are:
  - stronger grounded evidence on hard rows
  - broader structural coverage across non-company cohorts
  - measured promotion evidence from the new operator/report surfaces

## ITIL Reading

- service outcome: Nat gets a governed migration-review workbench
- incident to avoid: treating one lane outcome as justification for whole-set
  automation
- change posture: tiered service model with explicit stop conditions

## ISO 9000 Reading

Quality objective:

- maximize reviewer throughput without collapsing provenance or uncertainty

## ISO 42001 Reading

- human review remains primary for the non-Tier-1 lanes
- automation level must match evidence quality
- abstention and hold remain valid outputs

## ISO 27001 Reading

- bounded receipts and revision locking limit uncontrolled evidence drift
- explicit holds reduce unsafe action from weak evidence

## Six Sigma Reading

Primary defects this posture avoids:

- false “safe” migrations
- reviewer time wasted on manual source hunting
- hidden authority inflation from wiki-derived evidence
- misleading success claims from tiny safe subsets

## C4 View

### Context

- Wiki proposal surfaces and Wikidata statement bundles feed the review system.
- ITIR captures and enriches.
- SensibLaw classifies, splits, and verifies.
- Nat reviews and acts.

### Container

- revision capture
- migration pack classification
- reviewer packet layer
- split-plan / split-verification layer
- checked-safe export / after-state verification layer

## PlantUML

```plantuml
@startuml
title Nat End Product And Tiered Automation

Component(WIKI, "Wiki Proposal Surface", "Revision-locked input")
Component(PACK, "Migration Pack", "Classify rows")
Component(PACKET, "Reviewer Packet", "Review-only evidence bundle")
Component(SPLIT, "Split Verification", "Expected after-state checks")
Component(SAFE, "Checked-Safe Export", "Tier 1 bounded execution")
Component(REVIEWER, "Nat Reviewer", "Approves / reviews / holds")

Rel(WIKI, PACK, "constraints + context")
Rel(PACK, SAFE, "checked-safe rows")
Rel(PACK, PACKET, "split-required / review rows")
Rel(PACKET, REVIEWER, "review packet")
Rel(REVIEWER, SPLIT, "reviewed split")
Rel(SAFE, SPLIT, "after-state verification")
@enduml
```

## Immediate Planning Consequence

The next implementation priority is not broader blind online sampling.

The next execution shape, when the work is wide enough, is parallel
review-first lanes rather than a single monolithic worker loop.

It is:

1. grounding depth on representative hard packets
2. structural breadth on Cohort C and the other non-company lanes
3. measured batch/report evidence across those lanes
4. explicit automation graduation criteria with repeated-run evidence
5. only then additional packet attachment when a genuinely new split shape
   appears

That is the missing layer that makes the wider review-and-split goal truly
usable at scale.
