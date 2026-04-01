# Wikidata Nat Review Packet Attachment Coverage

Date: 2026-04-01

## Purpose

Record the first bounded expansion of Nat reviewer-packet attachment across
held split rows.

This is a coverage note, not a completion claim. It broadens the packetized
surface beyond the original single held row while staying inside the existing
review-packet contract and keeping the lane fail-closed.

## Scope

This note covers:

- the existing Nat review packet for `Q10403939`
- a second packetized held split row for `Q10422059`
- a third packetized held split row for `Q731938` (AstraZeneca) drawn from the live tranche
- nine wider-online reviewed rows from the live tranche
- two additional sidecar-backed pilot-pack split plans for `Q10416948` and
  `Q56404383`
- the shared review-packet contract surface

It does not cover:

- runtime attachment code
- follow-receipt coverage across the remaining held split rows
- new shared trackers
- post-edit verification
- any claim that the full held-row set is packetized

## Current Coverage State

Held split rows in the current Nat tranche:

- total held split rows: `53`

Packetized held split rows in this slice:

- packetized rows: `13`
- packetization coverage: `13 / 53`

That is the first actual coverage expansion beyond the docs-only checkpoint.
It now includes the original two held rows, the AstraZeneca held row, the
wider-online reviewed rows from the live tranche, and two additional
pilot-pack packets that carry the semantic sidecar. It is still partial.

## ZKP Frame

### O

- Nat lane reviewers
- ontology-group reviewers
- packet-attachment maintainers

### R

- broaden reviewer-packet attachment across held Nat split rows
- keep the surface bounded and reproducible
- preserve the split plan as the execution-facing baseline

### C

- this note only
- the existing Nat review-packet contract
- the existing single-row review packet
- the new attachment coverage index

### S

- the lane already has one pinned Nat review packet
- the lane now has a second packetized held split row
- the remaining held split rows are still not packetized

### L

- single-row packet
- multi-row attachment coverage index
- later broader packet coverage

### P

- candidate artifact: a bounded multi-row Nat review-packet attachment surface

### G

- docs first
- no speculative code
- no authority inflation from packet attachment
- no shared aggregator edits

### F

- the bounded gain is multi-row packet attachment, not completion

## What Has Expanded

The packet surface now includes:

1. the original packet for `Q10403939`
2. a second packetized held row for `Q10422059`
3. a third held-row packet for `Q731938` (AstraZeneca)
4. nine wider-online reviewed rows from the live tranche
5. two additional pilot-pack sidecar packets for `Q10416948` and `Q56404383`
6. a machine-readable index that records all attachments

This means reviewers can now inspect three held split rows and the wider live
tranche rows in packetized form, using the same contract family.

## What Is Ready for Reviewers

Reviewers now have:

- the original Nat packet surface
- a second Nat packetized held row
- the new AstraZeneca held row from the live tranche plus the surrounding
  wider-online rows
- two additional sidecar-backed pilot-pack packets
- a coverage index showing 13 / 53 packetized rows

In practical terms, that gives reviewers a broader packet surface without
pretending the whole tranche is packetized.

## What Is Still Missing

Still missing:

1. packet attachment across the remaining held split rows
2. broader follow-receipt coverage across the remaining held split rows
3. any claim that packetization is complete

So the lane is now broader, but still partial.

## Roadmap to Completion

The Nat packet-attachment lane still completes in bounded steps:

1. one pinned review packet
2. a second packetized held row
3. a multi-row attachment index
4. broader packet attachment across the held split rows
5. follow-receipt support
6. post-edit verification for any promoted subset

This note covers steps `2` through `4`.

## ITIL Reading

- service:
  Nat reviewer-packet attachment workflow
- change class:
  standard change
- operational meaning:
  contained packet coverage expansion for held split rows

## ISO 9000 Reading

- quality objective:
  make packet coverage explicit and reproducible
- quality result:
  reviewers can see exactly how far packet attachment has expanded and what
  remains

## Six Sigma Reading

Observed defect mode:

- one-off reviewer packets that do not generalize across the held row set

Control response:

- pin a second packetized held row and a coverage index before claiming
  broader packet attachment

## C4 / PlantUML

```plantuml
@startuml
title Wikidata Nat Review Packet Attachment Coverage

Component(contract, "Review Packet Contract", "Existing Nat review-packet contract")
Component(packet1, "Held Row Packet 1", "Q10403939")
Component(packet2, "Held Row Packet 2", "Q10422059")
Component(index, "Attachment Coverage Index", "13 / 53 packetized rows")
Component(reviewer, "Reviewer", "Nat / ontology reviewers")

Rel(contract, packet1, "supports")
Rel(contract, packet2, "supports")
Rel(packet1, index, "included in")
Rel(packet2, index, "included in")
Rel(index, reviewer, "shows coverage")

@enduml
```

## Exit Condition

This note is useful when reviewers can point to a bounded, reproducible
multi-row packet surface and still see that most held split rows remain
unpacketized.
