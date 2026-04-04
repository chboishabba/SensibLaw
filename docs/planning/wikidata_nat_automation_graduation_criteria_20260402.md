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

Current lane posture is now split:

- one exact Gate B family subset is promoted as bounded `Level 2` pilot-ready
- broader Cohort A is not promoted
- climate-family work has only reached a one-run seed state and should now be
  read as a migration-aware hold
- parthood-family work has advanced beyond seed state through bounded acquired
  artifacts, while current live same-family exports still remain blocked
- overall lane posture remains below Gate C

Current promotion provenance read:

- `family_one` is promoted by `baseline_runtime`
- `parthood_family_safe_reference_transfer_subset` is promoted by
  `supplied_acquired_artifact`
- no family is yet promoted by observed live same-family success in the
  current pinned real-world revisions

Current climate read:

- the climate blocker is not just "missing another revision"
- the lane is a controlled `P5991 -> P14143` migration protocol problem
- the exact climate row should be treated as `MIGRATION_PENDING` where the
  migration protocol is active but the required `P14143` after-state has not
  yet been observed in source reality
- `MIGRATION_PENDING` is explanatory state only and must not satisfy
  promotion, repeated-run, or second-witness rules

## Bounded Pilot Promotion Rule

When a Gate B family is promoted from repeated measured evidence, the default
promotion scope is bounded unless broader evidence explicitly says otherwise.

For the current Nat checked-safe path, the correct framing is:

- promote only the verified family subset
- do not infer readiness for broader Cohort A
- do not infer readiness for Cohorts B, C, D, or E
- do not infer backlog-wide blind automation readiness

Promotion wording should be explicit:

- pilot-ready for the exact verified family subset

## Migration-Aware Hold Rule

Some Nat families are controlled migration lanes rather than generic churn
lanes.

For those families, the evaluator and operator read should distinguish:

- `AWAITING_EVIDENCE`
  the lane should already have a second witness, but does not
- `MIGRATION_PENDING`
  the lane has a known upstream migration protocol and target after-state, but
  the required after-state is not yet observed in live source reality

Safe interpretation:

- `MIGRATION_PENDING` explains why a family is held
- it does not relax any promotion threshold
- it does not count as a second witness
- it does not convert expected-after-state into observed-after-state

Current application:

- climate-family rows in the `P5991 -> P14143` migration lane may be read as
  `MIGRATION_PENDING` when:
  - the migration protocol is active
  - the verifier still cannot find the required `P14143` after-state
  - no independent second witness has yet been acquired
- this is now a runtime state, not only a prose rule
- the climate intake contract now includes:
  - `same_family_after_state`
  - `cross_row_migrated_p14143`
  - `text_bridge_promoted_observation`
- the repo also now carries a bounded `climate_family_v2_live_p14143_subset`
  seed for migrated-row acquisition against live enterprise `P14143` examples

## P5991 Semantic Triage Rule

The wider `P5991` population must not be treated as a single direct-migration
class.

Rows should be triaged into:

- `direct_migrate`
- `split_required`
- `migration_pending`
- `out_of_scope`
- `needs_review`

Safe interpretation:

- only `direct_migrate` rows are eligible for automatic mainline execution
- `split_required` rows must decompose before migration
- `migration_pending` rows remain explanatory holds
- `out_of_scope` rows are excluded from the mainline claim
- `needs_review` rows abstain until semantics are clearer

This rule makes heterogeneity a first-class control surface and prefers
segmentation plus abstention over uniform automation pressure.

## Next Proving Priority

The next proving target should not be selected by narrative preference.

Current priority order:

1. first real family promoted through `live_same_family_acquisition`
2. climate recovery through migration-aware discovery or cross-source
   confirmation
3. any broader Gate C claim only after those paths are real

## Closed-Loop Migration Overlay

The Nat lane now has a bounded migration overlay in addition to promotion
state.

Execution-side lifecycle:

- `NOT_STARTED`
- `READY`
- `EXECUTED`
- `VERIFIED`

Safe interpretation:

- this overlay does not replace promotion state
- it answers a different question:
  whether a family is ready for migration work, has had a migration payload
  built/executed, and has then been verified again through the same control
  plane
- execution readiness is narrower than promotion:
  the family must be promoted and the target property must be live-backed
- current examples:
  - `business_family_reconciled_low_qualifier_checked_safe_subset` is
    execution-ready
  - climate is not execution-ready because it is `MIGRATION_PENDING`
  - parthood is not execution-ready because its current bounded target
    property is synthetic rather than live-backed

Execution payload boundary:

- payload generation is review-first
- the repo can now shape OpenRefine / QuickStatements-compatible rows from
  promoted checked-safe candidates
- the repo can now also emit explicit pre-execution contracts for those rows:
  canonical migration candidates, backend routing plans, receipt contracts,
  and post-write verification contracts
- this is not yet a claim of blind direct write execution
- the repo can now also ingest receipt-shaped artifacts and score
  post-write verification and execution proofs locally
- but a genuine operator receipt still requires an actual external action:
  a real review/export handoff, a real execution against Wikidata or an
  equivalent execution tool, and a real returned record of what was applied
- derived receipts from pinned exports remain useful proof surfaces, but they
  do not satisfy operator-real provenance by themselves

Current operational read:

- `parthood` proved family generality and acquired-artifact promotion
- `climate` proved migration-aware blocking
- the next leverage is higher-yield live target selection, not more threshold
  tuning
- the next operator-real leverage is provenance closure on receipts, not more
  local receipt formatting
- generalization forbidden without new measured evidence
- fail-closed posture preserved outside the promoted subset
- split verification is real
- packet and follow-depth support is real
- broad measured direct-safe stability is not yet demonstrated

So the honest current automation ceiling is:

- `Level 2` for the exact promoted family subset only
- below `Level 2` for the rest of the lane
- below Gate C for any broader automation claim

## Current Nat Read

The first bounded measured-automation family is now explicit:

- family scope:
  `Q1068745|P5991|1` and `Q1489170|P5991|1`
- promotion scope:
  bounded pilot-ready only
- generalization:
  forbidden without new measured evidence

The held second-family seams are also explicit:

- family seed:
  `climate_family_safe_reference_transfer_subset`
- current safe row:
  `Q10651551|P5991|1`
- current state:
  one truthful verification run only
- blocker:
  no second independent after-state artifact and no second safe row in the
  current pack

- family seed:
  `parthood_family_safe_reference_transfer_subset`
- current safe rows:
  `Q16572|P361|1`, `Q3700011|P361|1`, `Q980357|P361|1`
- current state:
  one truthful verification run only
- blocker:
  no second independent after-state artifact for that family yet
- acquisition posture:
  this is now the primary second-family proving target, and as of April 4,
  2026 its bounded seed is backed by live candidate rows rather than fixture
  placeholders
- live-route caveat:
  the current same-family live acquisition path is still blocked for all three
  rows with `verification_target_missing`, because this bounded family still
  migrates toward synthetic `P99999`
- bounded recovery path:
  a manual/acquired independent artifact for `Q16572|P361|1` now proves the
  family can enter `READY_TO_RERUN` through the existing acquisition runner,
  even though the live same-family path remains blocked
- bounded completion path:
  manual/acquired independent artifacts for the remaining two parthood rows
  now prove the entire family can reach `PROMOTED` through the same generic
  runner and convergence path
- bounded live-path completion:
  the same generic family acquisition plan can now drive a live revision sweep
  over recent Wikidata revisions, build revision-locked entity exports, and
  promote the family with `state_basis = live_same_family_acquisition` when
  those later revisions actually verify; this proves live-path capability
  without claiming that the currently pinned live exports already do so
- provenance read:
  the Nat state machine now separates family `state` from `state_basis`, so
  this parthood result is explicitly recorded as
  `supplied_acquired_artifact` rather than as a baseline or live same-family
  promotion

This means the lane has crossed Gate B locally for one exact family subset,
but has not crossed Gate C.

## Independence Rule

Repeated-run evidence must come from real separate artifacts, not synthetic
duplication of one source slice.

For Nat promotion purposes, two evidence paths are only independent when they
meet all of the following:

- different after-state artifacts or different revision-locked source bundles
- not mechanically duplicated from the same underlying artifact
- same candidate-level semantic conclusion
- replayable through the same verifier/governance path

Practical consequence:

- one clean run proves bounded local viability
- two clean but non-independent runs do not clear a gate
- promotion beyond a local family subset requires independent confirmation
- when a claim remains `SINGLE_RUN`, the next required input should be emitted
  as a confirmation intake contract that names the seen roots and the minimum
  independent artifact bundle needed for re-entry into the verifier path
- once such an artifact is supplied and accepted by the bounded acquisition
  runner, the family may move to `READY_TO_RERUN`, but promotion still depends
  on passing the same convergence and governance path as before
- state-machine outputs must preserve promotion provenance:
  `baseline_runtime`, `live_same_family_acquisition`, and
  `supplied_acquired_artifact` are distinct operational states even when the
  top-level family state is the same
- same-family acquisition only counts when the supplied revision-locked entity
  export survives `verify_migration_pack_against_after_state`; a merely new
  wrapper around an unchanged or drifted after-state does not qualify
- held second-family seeds may also emit a family acquisition plan that ranks
  their next bounded proving candidates without over-claiming broader
  production readiness

## Prioritized Roadmap To Complete

The shortest honest path from the current state to broader completion is:

1. keep the current two-row family frozen as already proved
2. make evidence independence explicit in the runtime and governance model
3. use the parthood-family acquisition plan as the primary proving path now
   that its real bounded candidate set is materialized
4. either materialize at least one additional independent evidence path for
   that second family through a non-synthetic target surface, or stop claiming
   the current same-family live path is viable
5. rerun the same verifier, proposal, evidence, and governance chain on that
   second family
6. only then assess whether Gate C is actually satisfied

This is a data and evidence problem now, not a missing-gates problem.

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
