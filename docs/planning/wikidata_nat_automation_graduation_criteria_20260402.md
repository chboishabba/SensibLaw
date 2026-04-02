# Wikidata Nat Automation Graduation Criteria

Date: 2026-04-02

## Purpose

Define explicit, auditable gates for graduating the Nat lane from review-first
operation to broader automation, and finally to moonshot-level blind
execution.

This is a governance document, not an implementation shortcut.

## Scope

Applies to the Nat `P5991 -> P14143` migration lane and its cohort branches.

Out of scope:

- policy edits that bypass current split/verification controls
- full-population blind execution before gate evidence is satisfied

## Graduation Ladder

`Level 0` Review-first only
`Level 1` Reviewer-assisted split execution
`Level 2` Family-scoped measured automation
`Level 3` Broad automation with strict holds/abstains
`Level 4` Moonshot blind migration bot

## Required Gate Families

Every graduation decision must clear all five families:

1. Evidence grounding
2. Claim-boundary reliability
3. Verification quality
4. Policy-risk containment
5. Operational control and rollback

Fail one family, fail the gate.

## Gate Criteria By Level

### Gate A: Level 0 -> Level 1

Must show:

- reviewer packets exist for representative split shapes
- bounded follow-depth evidence exists and is fail-closed
- split plans are verified on representative reviewed plans
- unresolved uncertainty remains explicit in packet outputs

Blocked if:

- packet evidence is mostly inferred without revision-locked anchors
- split verification exists only on one narrow shape

### Gate B: Level 1 -> Level 2

Must show:

- at least one backlog family has repeated measured direct-safe behavior
- after-state verification stays stable across repeated tranches
- false-positive incidence is below the family budget
- abstain/hold behavior remains active and effective

Blocked if:

- direct-safe yield is unstable between tranches
- repeated tranches collapse back to mostly `split_required`

### Gate C: Level 2 -> Level 3

Must show:

- automation works across more than one structural family
- policy-risk cohorts remain separated and governed
- cross-source disagreement handling is explicit and deterministic
- rollback and replay paths are validated end to end

Blocked if:

- automation gain depends on suppressing hold/abstain paths
- verification receipts are incomplete or non-replayable

### Gate D: Level 3 -> Level 4

Must show:

- broad coverage under bounded risk with sustained quality
- blind execution is safer than reviewer-gated execution for the promoted
  families
- complete auditability for source, split decision, and after-state receipts
- on-call rollback and kill-switch controls are proven

Blocked if:

- policy-risk families are still materially unresolved
- audit trails are incomplete or human-reconstruction dependent

## Core Metrics

Minimum tracked metrics for every candidate promotion window:

- direct-safe yield by family
- split-required rate by family
- hold/abstain rate and reason distribution
- after-state verification pass rate
- false-positive rate and severity
- rollback invocation and recovery success
- receipt completeness coverage

## Promotion Decision Contract

A promotion proposal must include:

- candidate level transition
- evidence window and sampled families
- metric summary with threshold comparison
- explicit risks and mitigations
- signed recommendation:
  - `promote`
  - `hold`
  - `revert`

No implicit promotion from narrative confidence.

## Machine-Checkable Evaluator

The first bounded evaluator surface now exists:

- runtime helper:
  `SensibLaw/src/ontology/wikidata_nat_automation_graduation.py`
- deterministic entrypoint:
  `evaluate_nat_automation_promotion(criteria, proposal)`
- tests:
  `SensibLaw/tests/test_wikidata_nat_automation_graduation.py`

Design constraints:

- fail-closed by default
- explicit failed checks for missing families/evidence/metrics
- blocker signals force hold/reject
- unknown gate ids reject immediately

Next bounded operator/control surface now also exists:

- CLI command:
  `sensiblaw wikidata automation-graduation-eval --criteria ... --proposal ...`
- deterministic report wrapper:
  `build_nat_automation_graduation_report(criteria, proposal)`
- pinned proposal fixtures:
  - `wikidata_nat_automation_promotion_proposal_gate_a_promote_20260402.json`
  - `wikidata_nat_automation_promotion_proposal_gate_b_hold_20260402.json`

Next bounded queue/index surface now also exists:

- deterministic batch wrapper:
  `build_nat_automation_graduation_batch_report(criteria, proposal_batch)`
- CLI command:
  `sensiblaw wikidata automation-graduation-eval-batch --criteria ... --proposal-batch ...`
- pinned batch fixture:
  `wikidata_nat_automation_promotion_proposal_batch_20260402.json`

This keeps operator triage deterministic across multiple proposals while
remaining fail-closed per proposal and at batch-summary level.

Next bounded measured-evidence surface now also exists:

- deterministic repeated-run scorecard:
  `build_nat_automation_graduation_evidence_report(criteria, proposal_batches)`
- CLI command:
  `sensiblaw wikidata automation-graduation-evidence-report --criteria ... --proposal-batches ...`
- pinned repeated-run fixture:
  `wikidata_nat_automation_promotion_proposal_batches_20260402.json`

Fail-closed readiness rule:

- any rejected proposal across repeated runs keeps readiness on hold
- any fail-closed proposal across repeated runs keeps readiness on hold
- mixed gate scope across repeated runs keeps readiness on hold
- insufficient repeated run count keeps readiness on hold

Next bounded governance-index surface now also exists:

- deterministic cross-snapshot index:
  `build_nat_automation_graduation_governance_index(criteria, evidence_snapshots)`
- CLI command:
  `sensiblaw wikidata automation-graduation-governance-index --criteria ... --evidence-snapshots ...`
- pinned snapshot fixture:
  `wikidata_nat_automation_evidence_snapshots_20260402.json`

Fail-closed governance rule:

- any not-ready snapshot keeps governance readiness on hold
- any rejected/fail-closed proposal totals keep governance readiness on hold
- mixed gate scope across snapshots keeps governance readiness on hold
- insufficient snapshot count keeps governance readiness on hold

Next bounded governance-summary surface now also exists:

- deterministic repeated-index governance summary:
  `build_nat_automation_graduation_governance_summary(criteria, governance_snapshots)`
- CLI command:
  `sensiblaw wikidata automation-graduation-governance-summary --criteria ... --governance-snapshots ...`
- pinned governance-snapshot fixture:
  `wikidata_nat_automation_governance_snapshots_20260402.json`

Fail-closed repeated-index governance rule:

- any not-ready governance index keeps summary readiness on hold
- any rejected/fail-closed totals in governance indexes keep summary readiness on hold
- mixed gate scope across governance indexes keeps summary readiness on hold
- insufficient governance index count keeps summary readiness on hold

## Current Read (Pinned)

Current lane posture remains below Gate B:

- review-first controls are strong
- split verification is real
- packet and follow-depth support is real
- broad measured direct-safe stability is not yet demonstrated

So the honest current automation ceiling is `Level 1`.

## ZKP Frame

### O

- Nat and ontology/workgroup reviewers
- ITIR/SensibLaw control-plane owners

### R

- safe, evidence-backed graduation to higher automation levels

### C

- reviewer packet lane
- split verification lane
- cohort automation lanes

### S

- good review-first maturity, insufficient broad automation maturity

### L

`L0 -> L1 -> L2 -> L3 -> L4`

### P

- enforce explicit gate checks instead of informal readiness claims

### G

- fail-closed default
- promotion only by multi-family evidence

### F

- missing broad, stable automation evidence beyond review-first strengths
