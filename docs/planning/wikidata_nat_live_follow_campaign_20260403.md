# Wikidata Nat Live-Follow Campaign

Date: 2026-04-03

## Purpose

Start exercising real online follow for the Nat lane in a bounded way.

The goal is not broad live population crawl. The goal is to take a small set
of representative Nat uncertainty classes and run the smallest useful live
follow that can collapse uncertainty faster than the current pinned-fixture
path.

## Why Now

The lane already has:

- review packets
- split and hold surfaces
- grounding-depth helpers
- operator queue/report/control surfaces
- bounded follow receipts in some packets

What it does not yet have is a current small live-follow campaign that feeds
those same packet and control surfaces with fresh evidence.

## Campaign Rule

Local packet context comes first.

Only run live follow when the packet or control surface already shows:

- unresolved pressure
- a likely next source class
- a bounded target

Do not run broad search just because a lane mentions Wikidata or Wikipedia.

## Campaign Categories

The first campaign should deliberately span several different Nat failure
classes rather than repeating one business-family split pattern.

### 1. Hard Grounding Packet

Purpose:

- confirm that current grounding-depth helpers can absorb fresher evidence from
  live follow without changing their review-first shape

Representative target:

- `review-packet:5bae90b4fcb444f6`
- `Q10403939`

Expected live follow:

- revision-locked evidence expansion
- deeper receipt or source excerpt above the current query-link summary

### 2. Split-Heavy Business Family

Purpose:

- pressure-test split-heavy packet follow where query-link evidence exists but
  still has unresolved uncertainty

Representative targets:

- `review-packet:041f7506c2efdeca`
- `Q738421`
- `review-packet:atrium-ljungberg-20260401`
- `Q10422059`

Expected live follow:

- expand from query-link receipt into bounded revision-locked or source-linked
  evidence
- verify split-axis and reference expectations against the currently reviewed
  bundle

### 3. Reconciled Non-Business Variance

Purpose:

- test whether live follow helps with variance-heavy rows outside the business
  family

Representative targets:

- `Q8646|P5991|4`
- `Q11661|P5991|1`

Expected live follow:

- bounded evidence around qualifier/reference variance
- class-local semantics confirmation before any migration-equivalence judgment

### 4. Policy-Risk Population Preview

Purpose:

- test whether live follow can reduce policy-risk uncertainty in Cohort C
  without breaking the review-first hold posture

Representative targets:

- `Q1000001`
- `Q1000002`

Expected live follow:

- qualifier-reference confirmation
- stronger evidence for why the item remains hold-only or can move into a
  narrower review path

### 5. Missing Instance-Of Typing Deficit

Purpose:

- test whether live follow helps resolve packet readiness and typing pressure
  for Cohort D cases

Representative targets:

- `review-packet:f451ac11e012b114`
- `Q1785637`
- `review-packet:041f7506c2efdeca`
- `Q738421`

Expected live follow:

- bounded evidence that helps confirm or narrow the next typing check
- not blind execution

### 6. Unreconciled Instance-Of Split-Axis Diagnosis

Purpose:

- test whether live follow helps explain unreconciled-instance ambiguity before
  wider automation assumptions

Representative targets:

- `Q10422059|P5991|5`
- `Q10403939|P5991|12`

Expected live follow:

- axis-specific evidence to support `review_structured_split` or `review_only`

## Preferred Source Order

1. revision-locked Wikidata or Wikipedia evidence already named by the packet
2. explicit query-link targets already cited in the packet
3. stable reference URLs already surfaced in packet review material
4. broader live search only if the packet still lacks a named source path

## Search Bounds

Each target should declare:

- trigger
- source class
- max hops
- stop condition

Default live-follow stop conditions:

- one authoritative excerpt that closes the current uncertainty
- two confirming receipts with no stronger conflicting evidence
- one bounded contradiction that proves the packet must stay hold/review-only
- max two hops from the packet's named source path

## Success Measure

For each target, compare:

- unresolved state before live follow
- unresolved state after live follow
- whether authority quality improved
- whether the result changed the next recommended review move

The campaign is successful if it improves packet or control-surface usefulness
without expanding into open-ended crawl behavior.
