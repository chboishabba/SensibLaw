# Wikidata Review/Split Assist User-Story Alignment

Date: 2026-04-01

## Change Class

Standard change.

## Purpose

Check whether the repo's user stories already say the right thing about the
current Nat/Wikidata lane:

- review and split is the real goal
- ITIR should help reduce reviewer uncertainty
- wiki pages and sandbox pages should be useful as revision-locked review
  artifacts
- cited references and followed links should improve reviewer speed without
  becoming hidden authority

## Result

Partial alignment existed, but it was not explicit enough.

What was already present:

- wiki material as navigational/review surface rather than direct authority
- provenance-first comparison and non-silent uncertainty
- Wikidata review as bounded queue/review support rather than autonomous edit

What was missing:

- an explicit user story that says ITIR should parse bounded wiki revisions,
  expose cited references/outbound links, and follow selected sources to reduce
  reviewer uncertainty in split-heavy cases
- an explicit coverage note that this exists only partially today

## Changes Made

- added `ITIR-US-17: Wiki Revision Review Assist` to
  `docs/user_stories.md`
- strengthened the `Wikidata editor / ontology reviewer` story in
  `SensibLaw/docs/user_stories.md`
- updated
  `SensibLaw/docs/planning/user_story_implementation_coverage_20260326.md`
  so the gap is explicit rather than implied

## ZKP Frame

### O

- Nat and related Wikidata working-group editors
- ITIR as the review/capture substrate
- SensibLaw as the migration/review runtime
- reviewers/operators who need faster split decisions with less ambiguity

### R

- keep the product honest about review-first/split-first goals
- make sure user stories explicitly support wiki-page parsing, bounded link
  following, and reviewer-assist surfaces

### C

- `docs/user_stories.md`
- `SensibLaw/docs/user_stories.md`
- `SensibLaw/docs/planning/user_story_implementation_coverage_20260326.md`
- existing wiki-revision, migration-pack, and split-verification docs

### S

- the repo already had strong doctrine but weaker explicit story wording here
- the Nat lane and split-verification branch prove the review/split direction
  is real
- the missing part was explicit story coverage for uncertainty reduction via
  bounded wiki parsing and reference following

### L

1. wiki page captured
2. revision locked
3. sections/spans parsed
4. cited refs / outbound links exposed
5. selected stronger-source follow receipts attached
6. reviewer sees bounded split/review packet

### P

- treat wiki parsing and link following as reviewer-assist infrastructure, not
  semantic authority
- keep it bounded, revision-locked, provenance-first, and fail-closed

### G

- no automatic Wikipedia/Wikidata edit execution from page text
- no hidden promotion from followed links into truth
- uncertainty reduction is allowed; silent authority substitution is not

### F

- product doctrine was ahead of explicit user-story wording

## ITIL Reading

- service: bounded review/split assist for Wikidata migration work
- change type: standard documentation/governance correction
- risk: low, because this clarifies intended operator support rather than
  widening execution
- backout: revert the story/coverage edits if the wording is later judged to
  overstate implementation

## ISO 9000 Reading

Quality objective:

- make the intended reviewer-assist behavior explicit and auditable

Quality controls:

- story says what the system should help with
- coverage note says what actually exists
- doctrine still separates review aid from semantic authority

## ISO 42001 Reading

Relevant AI-governance posture:

- human review remains primary
- uncertainty and abstention remain explicit
- followed sources are surfaced as evidence packets, not hidden model truth
- role clarity is preserved: ITIR assists; reviewers decide

## ISO 27001 Reading

Information-security posture:

- revision-locked artifacts reduce ambiguity about what was inspected
- bounded follow behavior reduces uncontrolled crawl/sprawl
- provenance and explicit unresolved states reduce accidental misuse of weak or
  drifting sources

## Six Sigma Reading

Primary defect classes this alignment is meant to reduce:

- reviewer overload from context-free split flags
- hidden authority inflation from wiki prose or followed links
- ambiguous source provenance in split-heavy review
- repeated manual searching when cited refs already exist

## C4 View

### Context

- Wikipedia/Wikidata pages are upstream proposal/evidence surfaces
- ITIR captures and structures them
- SensibLaw turns them into bounded review and split artifacts
- human reviewers decide what to do

### Container

- wiki revision capture / source-unit layer
- reference and link extraction layer
- bounded follow/receipt layer
- migration-pack / split-plan / verification layer
- reviewer-facing handoff/workbench layer

## PlantUML

```plantuml
@startuml
title Wiki Review/Split Assist Alignment

Component(WIKI, "Wiki Revision Surface", "Revision-locked page / sandbox")
Component(ITIR, "ITIR Capture + Parsing", "Sections, spans, refs, links")
Component(FOLLOW, "Bounded Follow", "Selected cited-source receipts")
Component(SL, "SensibLaw Review Runtime", "Migration packs, split plans, verification")
Component(REVIEW, "Reviewer Surface", "Review packet / split decision")

Rel(WIKI, ITIR, "capture + parse")
Rel(ITIR, FOLLOW, "selected refs/links")
Rel(ITIR, SL, "constraints + evidence")
Rel(FOLLOW, SL, "stronger-source receipts")
Rel(SL, REVIEW, "bounded split/review artifacts")
@enduml
```

## Current Honest Claim

The repo can now honestly say:

- review and split is the right mainline goal for the wider Nat lane
- ITIR should help by capturing/parsing wiki revision surfaces and by improving
  reviewer context
- generic cited-reference/link-follow assist is a desired user-story-backed
  capability, but only partially implemented today
