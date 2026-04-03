# Wikidata Nat Gap To Moonshot Program

Date: 2026-04-02

## Purpose

Make the current gap between the review-first Nat lane and the long-term blind
migration-bot moonshot explicit, measurable, and governable.

The point of this note is not to relabel the current lane as already solved.
The point is to say exactly what still has to be true before blind execution is
honest, and what the next priorities are to close that gap.

Companion gate specification:

- `SensibLaw/docs/planning/wikidata_nat_automation_graduation_criteria_20260402.md`
- `SensibLaw/tests/fixtures/wikidata/wikidata_nat_automation_graduation_criteria_20260402.json`

## Current State

The lane already has:

- bounded migration-pack classification
- split-plan generation and verification
- checked-safe export and after-state verification for bounded direct-safe rows
- reviewer packets with bounded follow receipts and semantic sidecar helpers
- Cohort C as a separate review-first live-preview and operator-packet lane
- a bounded grounding-depth helper for representative hard Nat packets
- a bounded Cohort B review bucket plus operator-packet helper
- a bounded Cohort D type-probing surface
- a bounded Cohort E diagnostics helper
- a fail-closed automation-graduation evaluator
- operator-facing surfaces above several of those helpers:
  - grounding-depth attachment surface
  - grounding-depth batch artifact
  - grounding-depth CLI plus batch review-packet report
  - grounding-depth evidence report
  - Cohort B operator packet
  - Cohort B operator queue
  - Cohort B operator report
  - Cohort B operator batch report
  - richer Cohort C operator evidence packet
  - Cohort C operator report
  - Cohort C operator report batch plus CLI
  - Cohort C broader measured evidence sample
  - Cohort D operator review queue
  - Cohort D operator report plus CLI
  - Cohort D operator report batch plus CLI
  - Cohort E diagnostics CLI/report
  - Cohort E diagnostics batch report
  - Cohort E grouped diagnostics summary
  - automation graduation report builder
  - automation graduation CLI
  - automation graduation batch evaluation CLI
  - automation graduation repeated-run evidence report
  - grounding-depth comparison/index report over multiple batches
  - Cohort B operator evidence index
  - Cohort C operator index over broader real-slice evidence
  - Cohort D review-control index over multiple operator batches
  - Cohort E aggregated disagreement/summary index
- automation graduation governance index over repeated evidence snapshots

The lane now also has one bounded measured-automation success:

- exact promoted family subset:
  `Q1068745|P5991|1` and `Q1489170|P5991|1`
- promotion scope:
  pilot-ready only for that exact family subset
- generalization:
  explicitly forbidden outside that subset

The lane also has one truthful second-family seed:

- family id:
  `climate_family_safe_reference_transfer_subset`
- current safe row:
  `Q10651551|P5991|1`
- current state:
  one-run hold, not promotion-ready

The lane also now has a concrete missing-evidence intake surface:

- single-run claims can emit a machine-readable confirmation intake contract
- that contract states exactly which candidate needs new evidence, which root
  artifacts are already seen, and what a new revision-locked artifact bundle
  must contain before it can enter the same verifier and convergence path
- those family-scoped intake contracts can now be aggregated into one intake
  backlog surface, so missing evidence is measurable across multiple held
  families instead of being tracked family-by-family only

The lane does not yet have:

- broad measured direct-safe yield across the wider backlog
- claim-boundary grounding strong enough to remove reviewer dependence for hard
  rows
- stable policy handling across the non-company cohorts
- quantitative evidence that blind execution would be safer than reviewer-gated
  execution
- broader operator/governance indexes that stay stable under repeated batch
  runs and disagreement clustering

## Moonshot Definition

The P0 moonshot is:

- a blind migration bot that can process the full `P5991 -> P14143` backlog
  without per-row human review while staying within the repo's provenance,
  qualifier, reference, and after-state governance boundaries

That moonshot is only valid if it can do all of the following at production
scale:

- classify rows correctly
- preserve qualifiers and references
- decompose split-heavy rows correctly
- abstain or hold on policy-risk cases
- verify after-state automatically
- expose enough evidence for audit after the fact

## Gap To Moonshot

The current gap is not "missing one more parser feature." The current gap is
the distance between:

- one bounded promoted family subset, plus a strong review-and-split workbench
- and a trustworthy blind executor

That gap currently has five major classes:

1. Evidence grounding gap
   The packets and semantic sidecars reduce uncertainty, but they do not yet
   ground enough revision-locked evidence to support broad blind promotion.

2. Claim-boundary gap
   The lane can surface likely split axes and candidate boundaries, but it does
   not yet prove that those boundaries are stable enough for wide blind
   execution.

3. Coverage gap
   Packetization, split verification, and safe verification are real, but they
   do not yet cover enough of the structurally different backlog families to
   justify moonshot-level trust.

   More specifically now:

   - family one is real and bounded
   - family two is only a seed
   - the missing ingredient is independent confirmation across a second
     structural family

4. Policy-risk gap
   Cohorts C, D, and E are still review-first branches. They are important
   because they expose the cases most likely to break blind execution.

5. Quality-management gap
   The repo still needs explicit promotion gates and stop conditions that say
   when a lane may graduate from review-first to semi-automated to blind.

## Staged Program

### Stage 0: Current

- review-first
- split-first
- fail-closed
- bounded safe automation only

### Stage 1: Grounded Review Workbench

Goal:

- make reviewer packets strong enough that difficult rows are decided from a
  compact evidence bundle rather than manual re-research

Exit criteria:

- more revision-locked evidence in packets
- stronger claim-boundary mapping
- cross-source agreement/disagreement surfaces on representative hard rows

### Stage 2: Semi-Automated Split Execution

Goal:

- let the system propose, verify, and package split plans tightly enough that
  human approval becomes fast and narrow

Exit criteria:

- representative split families verified repeatedly
- reviewer packet plus split verifier covers the dominant hard-row patterns
- policy-risk branches remain explicit and bounded

### Stage 3: Measured Broad Automation

Goal:

- prove that some larger backlog families can move with no per-row review

Exit criteria:

- stable direct-safe yield on broad samples
- stable after-state verification
- explicit false-positive budget small enough to justify blind action on that
  family

### Stage 4: Blind Migration Bot Moonshot

Goal:

- full-lane blind execution with auditability and abstention

Exit criteria:

- broad family coverage
- explicit hold/abstain reliability
- production-grade quality and risk controls

## Immediate Priorities

The next priorities should close the largest moonshot gap, not just broaden the
same company-heavy pattern or keep polishing the first bounded family.

1. Make evidence independence explicit.
   The next gating problem is independent confirmation, not family-one polish.
   The lane should expose which evidence paths are genuinely independent and
   which are just restatements of the same artifact.
   This now includes an executable intake contract for single-run claims, so
   "missing evidence" is an artifact-level request rather than only a hold note.

2. Materialize a real second family.
   Climate is the current seed, but it does not yet have enough independent
   safe evidence. Either strengthen that seed honestly or build a different
   structurally distinct family.

3. Drive second-family evidence through the same promotion path.
   Follow depth, claim boundaries, cross-source alignment, reviewer actions,
   and bounded variant comparison should justify or block promotion decisions,
   not just exist as diagnostics. For family two, the exact target is repeated
   verifier-backed evidence plus the same proposal, evidence, and governance
   path already used for family one.

4. Keep graduation claims local until Gate C is real.
   The repo already has explicit criteria. The task now is not to redefine
   them, but to avoid overclaiming from the first family.

5. Keep parallelism lane-shaped.
   When the work is broad enough, assign one nonblocking lane per worker, but
   only when the lanes are genuinely disjoint and useful.

## Current Roadmap To Close The Gap

### Priority 1: Independence and Second-Family Evidence

- add an explicit independence test for promotion evidence
- separate "same artifact restated twice" from true repeated independent runs
- add a confirmation-oriented follow path that hunts independent evidence
  instead of merely more edges
- use the climate-family seed as the first proving target, but stop if no
  truthful second run exists

### Priority 2: Grounding

- deepen revision-locked evidence receipts on representative Nat packets
- tighten claim-boundary mapping on split-heavy representative rows
- improve cross-source agreement/disagreement views for reviewer confidence
- use `src/ontology/wikidata_grounding_depth.py` as the first executable
  grounding-depth surface rather than relying on doc-only packet examples
- attach grounding depth to actual review/operator packets where packet ids and
  qids align, so reviewers consume the evidence as part of the packet rather
  than as a separate note
- prefer batch/report surfaces over one-off packet notes once a helper is
  stable enough to aggregate multiple representative packets
- once a batch/report surface exists, prefer a CLI-backed operator path so the
  evidence surface is reproducible instead of doc-local only

### Priority 3: Structural Breadth

- exercise Cohort C live preview and operator packet on broader live candidates
- keep Cohorts D and E review-first, but make their backlog shape measurable
  through explicit helper surfaces
- use Cohort B operator packets for reconciled non-business classes before
  widening company-family packet coverage again
- only expand company-family packet coverage again if a genuinely new split
  shape appears
- when a non-company lane already has a helper, prefer converting it into a
  deterministic operator-facing queue/report surface before widening the lane
- once a queue/report surface exists, prefer CLI-backed reproducibility over
  additional prose-only notes
- once a single-report CLI exists, prefer bounded batch reporting over
  additional isolated examples
- once a first batch/report surface exists, prefer broader measured evidence
  across multiple representative cases rather than new one-off examples

### Priority 4: Promotion Gates

- define measurable lane graduation criteria
- pin false-positive / abstain / hold expectations
- keep proposal evaluation reproducible with CLI-backed single-proposal and
  batch-proposal assessments
- make safe automation promotion dependent on those criteria
- use `evaluate_nat_automation_promotion(...)` as the bounded fail-closed
  promotion checker rather than relying on narrative readiness claims
- require machine-readable promotion reports when a gate is assessed so later
  audit does not depend on hand-written summaries
- where possible, expose those reports through a deterministic operator CLI so
  promotion assessment can be rerun without ad hoc scripting
- once single and batch proposal evaluation exist, prefer repeated-run
  evidence reports over stronger readiness claims

### Priority 5: Moonshot Readiness

- only after the earlier stages are stable, evaluate whether any broad family
  is ready for blind execution

## ZKP Frame

### O

- Nat and related Wikidata reviewers
- ITIR as review-packet and evidence-grounding substrate
- SensibLaw as classification, split, and verification runtime

### R

- close the gap between a governed review workbench and a trustworthy blind
  migration executor

### C

- migration-pack runtime
- split-plan and split-verification runtime
- reviewer packets and semantic sidecars
- Cohort B/C/D/E review lanes

### S

- one bounded `Level 2` family subset is now real
- the rest of the lane still has a weak basis for broad blind execution

### L

1. review-first
2. family-scoped measured automation
3. multi-family measured automation
4. blind migration bot moonshot

### P

- close the moonshot gap through staged grounding, breadth, and explicit
  promotion gates rather than by relabeling the current lane as already blind
  ready

### G

- fail-closed remains the default
- blind execution must be earned by evidence
- policy-risk cohorts remain separate until proven otherwise

### F

- the main gap is now independent second-family evidence, not lack of one more
  packet field

## ITIL Reading

- service strategy:
  move from review-assist service to higher-autonomy execution service only
  when quality controls are proven
- change management:
  use stage gates rather than rhetorical upgrades in automation claims

## ISO 9000 Reading

- quality objective:
  improve reviewer throughput now while building evidence that automation is
  actually correct later
- nonconformity to avoid:
  claiming automation maturity before the defect picture is understood

## ISO 42001 Reading

- human oversight remains primary until blind action is justified
- the automation level must stay proportional to evidence quality

## ISO 27001 Reading

- revision locking, bounded receipts, and after-state verification reduce
  unsafe action from drift or weak evidence

## ISO 27701 Reading

- keep followed-source and packet evidence bounded and auditable
- do not widen collection scope beyond the narrow review need

## ISO 23894 Reading

- treat blind migration as a higher-risk operating mode that requires explicit
  controls, residual-risk visibility, and conservative promotion gates

## NIST AI RMF Reading

- govern:
  define explicit automation graduation criteria
- map:
  identify which cohorts carry the largest harm if misclassified
- measure:
  quantify safe yield, abstain quality, and split correctness
- manage:
  promote only the families that repeatedly meet the controls

## Six Sigma Reading

Primary defects to reduce before moonshot promotion:

- false-safe migration decisions
- incorrect split boundaries
- policy-risk rows forced through the wrong lane
- reviewer packet gaps that hide decisive evidence

## C4 View

### Context

- Wiki proposal and source surfaces provide bounded context.
- ITIR assembles evidence and reviewer packets.
- SensibLaw classifies, splits, verifies, and measures promotion readiness.
- Nat and related reviewers remain the current authority gate.

### Container

- evidence grounding layer
- packet and sidecar layer
- migration-pack classification layer
- split verification layer
- promotion-gate and after-state verification layer

## PlantUML

```plantuml
@startuml
title Nat Gap To Moonshot Program

Component(WORKBENCH, "Review Workbench", "Current review-first lane")
Component(GROUND, "Evidence Grounding", "Revision-locked receipts + claims")
Component(SPLIT, "Semi-Automated Split", "Verified split assistance")
Component(GATES, "Promotion Gates", "Measured graduation criteria")
Component(MOONSHOT, "Blind Migration Bot", "P0 moonshot")

Rel(WORKBENCH, GROUND, "deepen evidence")
Rel(GROUND, SPLIT, "support narrower human approval")
Rel(SPLIT, GATES, "measure promotion readiness")
Rel(GATES, MOONSHOT, "promote only stable families")
@enduml
```

## Immediate Planning Consequence

The next roadmap should not be "more packet shape" and it should not be "more
company rows by default."

It should be:

1. grounding depth on representative hard packets
2. structural breadth on Cohort C and the other non-company lanes
3. explicit automation graduation criteria
4. only then broader moonshot-readiness claims
