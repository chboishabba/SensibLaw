# Wikidata Nat End Product And Tiered Automation

Date: 2026-04-01

## Purpose

State the full intended end product for Nat's `P5991 -> P14143` lane in plain
operational terms, and make explicit that full pipeline coverage is the real
goal, not blind full-population execution.

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

- not a blind migration bot
- not a vague queue of hard rows
- but a governed backlog-processing system with different lanes for different
  levels of certainty

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
- The generic reviewer packet contract/parser/follow-receipt lane is not yet
  implemented.
- Cohort C remains a separate review-first branch.

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

### G

- full backlog coverage is allowed
- blind full-population execution is not the target

### F

- the main missing piece is the generic reviewer-packet layer that compresses
  hard review cases without overclaiming authority

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

1. generic reviewer-packet contract
2. bounded parser
3. bounded follow receipts
4. packet attachment to held Nat split rows

That is the missing layer that makes the wider review-and-split goal truly
usable at scale.
