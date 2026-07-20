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

### Statement geometry and family context

The migration classifier operates at two distinct levels. A current Wikidata
claim GUID is atomic; sibling claims with the same subject/property are family
context, not evidence that any one GUID is overloaded.

```text
statement-level
  one GUID -> one quantity/value and its own qualifiers, rank, and references

statement-family-level
  sibling GUIDs -> scope/year partition, total/component relation,
  duplicates, overlap, and coverage context
```

Several separately stated scoped components plus a separately stated total are
therefore not split-required merely because their values or qualifiers differ.
Each GUID must be assessed independently for a property substitution. Family
context may record:

```text
scope_partition_state:
  already_partitioned | overloaded | overlapping | incomplete | unknown

total_component_relation:
  exact_reconciliation | approximate_reconciliation | contradiction |
  no_total | not_comparable

split_requirement:
  none | existing_partition_preserved | new_split_required |
  manual_reconstruction
```

Likewise, a `P580`/`P582` interval whose endpoints resolve to the same
reporting year is one annual statement shape, not two time values requiring a
split. A split is warranted only when one GUID contains genuinely competing
years, a multi-year/partial interval, or another independent semantic axis.

`Q101416961@2419927005` is the regression case: four separate `P5991` GUIDs
contain three scoped components and an unscoped total; the components sum
exactly to the total. A July 2026 three-row discovery page incorrectly
classified three atomic claims as Family B because it treated sibling
multiplicity as in-claim overload and omitted the fourth sibling from the
classifier input. Those packets are retained as `rejected_classifier_error`
evidence, not as a confirmation, trusted member, or invariant contribution.

Discovery may select GUIDs, but classification must hydrate every
source-property sibling for each selected pinned entity revision. Page
selection controls which atomic candidates are emitted, not whether family
context is complete enough for a total/component or duplicate inference.

## Climate-Domain Structural Pressure

Nat's `P5991 -> P14143` comparison is already a domain-specific pressure
(DSP) operation. It compares an observed statement with the admissible climate
/ GHG statement shape defined by the documented target model and migration
policy:

```text
subject typing + value + unit + qualifiers + references + time/scope structure
-> climate-domain expected statement shape
-> residual pressure -> Family A/B/C/D/E disposition
```

The first runtime carrier is now implemented as a generic
`DomainPressureAssessment` on each generated migration candidate. It records
separate target-model, subject-type, qualifier, reference, temporal, split,
and peer-cohort residuals. The existing A--E result is retained as the review
disposition, rather than being the only explanation. The assessment remains
diagnostic-only and has no direct promotion or edit consequence; peer-cohort
pressure is explicitly unresolved until governed trusted-cohort admission is
implemented.

This is not merely a frequency model over company items. The five-item pilot
(Handelsbanken, Swedish Inspectorate of Auditors, Swedish Agency for Government
Employers, Akademiska Hus, and Atrium Ljungberg) was selected as a
policy-anchored migration pack: it tests whether existing `P5991` statements
already conform to the `P14143` model, require splitting/repair, or must remain
held. It is not a generic organisation-cohort definition.

Comparable revision-pinned statements add a second, distinct pressure source:

```text
authoritative/model pressure
  documented climate model and migration policy

peer-cohort pressure
  recurring structure among comparable observed statements
```

Receipts must retain these grounds separately. A useful result therefore names
`subject_type_pressure`, `target_model_pressure`,
`qualifier_reference_pressure`, `temporal_split_pressure`, and any
`peer_cohort_pressure`; peer frequency cannot override the target model or
reviewer policy.

### Governed invariant learning

The climate-domain invariant is not static. It begins with the documented
target model, migration policy, and admissible subject type, then is refined by
reviewed, revision-pinned conforming cases:

```text
initial policy model
-> candidate comparison and review
-> governed confirmation
-> admission to trusted conforming cohort
-> revised empirical signature
-> better-qualified comparison of later candidates
```

The effective invariant is `I_policy intersect I_confirmed_cohort(n)`, while
retaining conditional branches for year, scope, methodology, jurisdiction, and
subject subtype. This distinguishes normative requirements from empirical
regularities, legitimate variation, and legacy noise.

Only `confirmed_model_conformant`, `confirmed_conformant_after_split`, and
`confirmed_conformant_after_repair` may contribute. Held, ambiguous,
unresolved, manual-reconstruction, or coverage-incomplete cases do not train
the cohort. Each admission and recomputation needs a revision-pinned
contribution receipt and invariant-revision receipt, so similarity to an
unreviewed cohort can never become circular evidence of conformance.

The shared runtime contract uses four generic artifacts:

```text
TrustedConformingMember
  candidate ref + pinned source revision + reviewer decision/authority
  + admitted feature contributions + coverage state

InvariantContributionReceipt
  why that reviewed member was admitted (or rejected) at this invariant revision

DomainInvariantSnapshot
  policy requirements + admitted members + empirical feature counts
  + conditional branches + exception/noise records + coverage requirements

InvariantRevisionReceipt
  previous snapshot + admitted contribution receipts + resulting snapshot
  + reviewer authority
```

Admission is fail-closed. A runtime record may enter the trusted cohort only
when it names a supported confirmed disposition, a review-decision receipt, a
review authority, a revision-pinned source, and observed coverage. The shared
carrier does not infer any of these from a Family A/B/C classifier output. In
particular, the live Family-B discovery page is not eligible until a reviewer
approves its split result and emits an explicit confirmation record.

That confirmation is a separate generic artifact, not a mutation of a review
packet. It names the reviewed candidate, source revision, decision/packet
reference, reviewer authority, coverage state, and a supported confirmed
disposition. For a Family-B case it also names the approved split plan and the
resolved structural features that are safe to contribute. The confirmation has
no edit or promotion effect: it is solely the explicit bridge from a
reviewer-approved candidate to a `TrustedConformingMember` input.

The cohort may reveal an underspecified policy model, a valid conditional
branch, an exception class, or an anomalous supposedly conforming item; it
cannot override the documented target model or reviewer policy.

### First live discovery tranche

Before trusted-cohort admission, the next runtime input is a deterministic,
bounded WDQS discovery page.  It is statement-level rather than QID-only and
starts with the `company_direct` stratum:

```text
direct P31 company/business/enterprise
+ P5991 statement
+ no P14143 statement already present
```

The discovery manifest records query/version/hash, retrieval time, ordering,
page/cursor, statement GUIDs, rank, direct P31 values, and target-property
coexistence.  Each discovered row is then reconciled against one
revision-pinned entity export.  Only an unchanged, still-present source
statement may be classified.  A live result that changed, disappeared, or
could not be revision-pinned remains visible as a reconciliation outcome but
does not enter A--E classification.

The initial policy invariant is normative: P14143 documentation and
constraints, the documented climate model, and Nat's migration policy.  The
small existing target-property population is not treated as an empirical
invariant.  Only independently reviewed conforming migrations can later add
empirical evidence through the governed cohort-admission path above.

The first live smoke page ran on 2026-07-16 with a three-statement bound. All
three discovered preferred `P5991` statements reconciled at entity revision
`2419927005` for `Q101416961`, whose direct `P31` is business. An earlier
classifier version incorrectly labelled them Family B; after complete sibling
hydration and atomic-statement correction they are Family-A
`safe_with_reference_transfer` candidates. This is still not a review
decision, migration, trusted-cohort admission, or empirical invariant
contribution.

### Corrected live-page packets and residual topology

The compact packet surface covers every reconciled candidate in a bounded live
page. It has three review shapes, all projected from the same generic
`TypedResidualProfile`:

```text
model-conformance candidate
  confirm conformant
  reject conformance
  hold unresolved

decomposition candidate
  confirm split plan
  reject split plan
  request revised split
  hold unresolved

family-conflict hold
  confirm hold
  request reconstruction
  mark legitimate exception
  hold unresolved
```

Each packet presents the source statement GUID and pinned subject revision,
source statement family, years/scopes/methods, qualifier/reference carry plan,
coverage limits, and its exact residual evidence. A decomposition packet adds
the proposed target-statement decomposition. A conflict packet names the
affected GUIDs, scope relationship, numeric reconciliation, and counterevidence
instead of pretending that it has a safe split plan.

The current corrected 25-GUID page contains 25 reconciled candidates: nine
model-conformance candidates, nine `scope_overlap` holds, and seven
`component_total_contradiction`/period-conflict holds. Review intake must emit
all 25 packets. A safe row is eligible for a later explicit confirmation; a
safe classifier label does not hide any attached family warning, which the
reviewer must clear before confirmation. A hold is not eligible to train the
invariant merely because it has been packed.

The packet is not a second classifier.  Both it and the later residual graph
must project the same generic `TypedResidualProfile`, built from the candidate
`DomainPressureAssessment` and explicit context-admissibility gates.

```text
TypedResidualProfile
  model, subject, qualifier, reference, temporal, scope/split residuals
  coverage masks and context gates
  -> reviewer packet projection
  -> typed residual graph
```

The graph keeps four distinct edge meanings: admissible structural similarity,
typed incompatibility, masked/inadmissible analogy, and unknown due to
coverage.  It may later propose review-only split, merge, disjointness, bridge,
nearby-class, exception, misclassification, or abstraction candidates. It does
not assign a class, merge/redirect classes, revise an invariant, or mutate
Wikidata. A reviewed row can become an invariant contribution only through a
supported confirmed disposition. A decomposition confirmation additionally
requires an approved split-plan reference. Rejected, held, unresolved, and
coverage-incomplete rows remain reconstructable evidence but never train the
invariant.

An ontology-class merge is not inferred from a similar Family-B residual
profile.  Before a direct merge can be reviewable, the generic proposal layer
must establish adequate coverage, normative compatibility, no typed or
conditional obstruction, substitutability of affected surrounding relations,
bounded downstream impact, and complete provenance transfer.  If those checks
do not all pass, the correct Nat-facing result is a review-only alternative
such as shared-superclass, bridge-class, conditional-distinction, alias-only,
held, blocked, or insufficient-coverage—not an automated merge.

The corrected three-row page emits three model-conformance packets and no
conflict/decomposition packet. Its graph contains no peer relationships because
there are not yet independently confirmed members. This is a useful fail-closed
baseline for later graph population.

### Immutable invariant replay after a reviewed conforming result

The first governed learning event is intentionally small: a reviewer may
confirm one model-conforming migration, a repaired result, or an approved
decomposition. A split contributes the resulting conforming target-statement
shapes rather than the malformed source bundle. The operational chain is:

```text
revision-pinned P5991 source family
-> explicit reviewer confirmation (and approved split plan when relevant)
-> TrustedConformingMember
-> InvariantContributionReceipt
-> DomainInvariantSnapshot I1
-> caller-supplied reassessment of remaining candidates against I1
-> new TypedResidualProfiles and graph projection
```

The original assessment, packet, profile, and `I0` graph are immutable. A
replay receipt must name their source references, the new invariant snapshot,
the same candidate and pinned source revision, and the resulting comparison
transition. It may report that an old `unknown_due_to_coverage` relation
remains unknown, becomes an admissible similarity, or becomes an admissible
incompatibility; it must not rewrite history as if `I1` had existed when `I0`
was reviewed.

The shared replay carrier accepts a supplied reassessment rather than deriving
climate semantics from empirical counts. The climate profile decides whether a
trusted target-statement shape grounds its peer-cohort residual; the generic
core validates identity/revision continuity, retains both profiles, projects a
new graph, and records the transition. This keeps future GWB, AU, Brexit,
Affidavit, city/capital, and ontology-review consumers on the same mechanism.

#### First approved contribution: Q101416961

On 2026-07-16, the reviewer authority `reviewer:GPTofJohl` explicitly
confirmed `Q101416961|P5991|1` at `Q101416961@2419927005` as
`confirmed_model_conformant`. The source GUID is
`Q101416961$FA70FC6A-B0CD-4838-8475-375506C8B6FB`; the proposed target
predicate is `P14143`.

The decision is narrowly grounded in the pinned evidence: an annual 2024
entity-level value, `P459` GHG Protocol method, compatible source reference,
and complete four-statement sibling-family coverage. Its scoped components
reconcile exactly to the stated total; the review found no overlap,
contradiction, temporal conflict, or new split requirement. The approved
contribution records the resulting target-statement shape only. It does not
assert that the old predicate is true, execute a Wikidata edit, promote a
claim, or authorize migration execution.

The approved object is one atomic source statement, but its conformance is
established partly by a complete sibling-family witness. A trusted contribution
therefore retains two non-interchangeable identities:

```text
selected candidate statement
+ pinned family-conformance witness
→ trusted component shape under family context
```

Generic trusted-member and contribution receipts must carry a
`conformance_context_ref`, `contribution_scope = selected_candidate_only`, and
a `dependency_group_ref`. For this case the witness records all four source
GUIDs, the selected GUID, aligned period/method/unit evidence,
`already_partitioned` scopes, `exact_reconciliation`, and complete family
coverage. This neither approves the siblings nor treats the selected component
as if it were assessed in isolation. Empirical snapshots must also distinguish
statement-shape contributions from independent family/entity observations, so
several statements in one report cannot dominate a cohort merely because they
have distinct GUIDs.

The initial temporary I1 files were emitted before this witness field existed.
They remain historical output. The witness-aware reissue is now at
`/tmp/nat-packets-live-25/invariant_i1_family_witness/`: it has a distinct
family-conformance receipt, review confirmation, trusted member, contribution,
I1 snapshot, and immutable replay. The new snapshot is
`domain-invariant:df866ca204c0d6e9f69f6b25f633be8981522fa196f55abfebbef62ecc3c61f6`;
the replay retained all 24 remaining candidates without retroactively changing
a residual transition.

### 100-statement online dry-run checkpoint

On 2026-07-16, a revision-pinned `company_direct` WDQS page of 100 source
statements across seven entities reconciled every discovered GUID to its entity
export. It produced 78 model-conformance packets and 22 family-conflict hold
packets; the underlying current classifier labelled 30 rows `A`, 57 `D`, and
13 `E`. These are review/dry-run surfaces, not migration approvals.

All 100 families had complete supplied sibling coverage, but all 4,950 pairwise
typed-residual-graph edges remained `unknown_due_to_coverage`: one
family-witnessed contribution does not establish a comparable independent peer
cohort. The live artifact is `/tmp/nat-packets-live-100/`, with query hash
`71bd5e84a3b7a96c6955696f7b1fa39394018470b342187a21f0fe8646504586`.

This creates the first empirical `I1` snapshot. The other 24 candidates are
reassessed as new immutable `I1` records while their `I0` assessments and graph
remain unchanged. One trusted, explicitly scoped component shape within this
four-statement reconciled family is not enough to infer peer compatibility for
differently scoped or conflicted rows, so those rows
must remain unresolved unless the profile can establish a comparable condition
from their own pinned evidence.

### From reviewed examples to bounded bulk migration

The endpoint is a governed, versioned migration contract—not a similarity-led
rename of every `P5991` statement. An exact match may eventually be transformed
only when its subject, annual entity-level meaning, value/unit, period, method,
scope, rank, references, and complete sibling-family context satisfy an
approved rule detector without collision, overlap, or contradiction.

```text
reviewed structural family
→ versioned transformation rule + exact applicability detector
→ whole-backlog dry-run coverage report
→ stratified false-positive checks and rule approval
→ revision-pinned migration manifest
→ canary / bounded batch execution with preflight and postflight checks
```

Reviewed examples contribute candidate rules, never broad authority by
resemblance. Each rule needs diverse confirmed positives, near-miss negatives,
and explicit coverage evidence. A later manifest must name source GUIDs and
revisions, target statements, qualifier/reference transfer, exclusions,
preconditions, postconditions, and rollback/reconciliation information. The
generic runtime now has a dry-run `TransformationRule` and
`RuleCoverageReport` carrier: profiles supply detector outcomes while the core
validates rule references and reports exactly-one, review/repair, conflicting,
no-rule, and incomplete-coverage outcomes. It has no execution-manifest or
edit capability. Nat-specific rule definitions, full-backlog discovery, and
rule approval remain pending.

### Sprint 1: contract discovery and backlog coverage

Rule calibration and backlog measurement are one iterative sprint. Rules must
not be designed from a small hand-picked sample and only later exposed to the
population. The loop is:

```text
bounded live page
→ identify a structural family
→ review independent positives and adversarial near-misses
→ refine an exact detector contract
→ rerun cumulative dry-run coverage
```

The first candidate catalogue is:

- `A1 atomic_annual_total`: one annual entity-level total with admissible
  subject, quantity/unit, method, references, and no sibling-family conflict;
- `A2 atomic_scoped_component`: one explicitly scoped atomic statement under
  complete, non-overlapping, coherent sibling-family coverage;
- `A3 already_separated_annual_series`: several independently conforming
  annual statements whose periods are distinct and non-overlapping;
- `B1 overloaded_source_statement`: one source statement genuinely encodes
  multiple target semantic units and therefore needs an approved split plan;
- `C1 repairable_model_incompleteness`: target semantics are otherwise
  established but one recoverable method/scope/qualifier defect remains;
- explicit `D/E` exclusion regions for out-of-domain subjects, product or
  intensity semantics, overlap, contradictory totals, unresolved periods, and
  malformed legacy bundles.

These labels are profile configuration over generic transformation-rule and
detector-result carriers. A legacy classifier label such as `A` is neither a
rule match nor migration authority. Every detector emits predicate-level
states and reason codes, preserves its dependency group, and abstains when
family coverage cannot prove the contract. In particular, a statement-level
safe row inside a whole-family overlap or unresolved multi-period structure
does not match `A1` or `A2` merely because its own qualifiers look valid.

The cumulative inventory must assign every candidate to exactly one dry-run
coverage outcome:

```text
exactly_one_candidate_rule
review_or_repair_rule
multiple_conflicting_rules
no_known_rule
coverage_incomplete
explicitly_out_of_target_domain
```

It must aggregate by rule, dependency group, subject type, family shape,
qualifier/year/method/unit/reference pattern, and conflict type. Candidate
rules remain review-only. Only a separately reviewed rule may later generate
a non-executing canary manifest, and similarity or spectral proximity can
nominate a rule but can never satisfy its applicability contract.

Progressive live pages must also remain operationally honest. Revision/export
requests use bounded retries, respect a server `Retry-After` response, and may
apply a configured inter-request delay. A page that exhausts retries is failed,
not partially counted in cumulative coverage.

Statement pagination uses a composite `(subject QID, statement GUID)` cursor.
A QID-only cursor can skip sibling statements when a page boundary falls
inside one entity, so such pages are bounded samples rather than admissible
cumulative inventory. Every page records the next composite cursor and the
cumulative pass must reject overlaps or gaps before publishing backlog counts.
The generic cumulative report preserves every page report reference, verifies
cursor continuity and candidate uniqueness, and records whether the final page
actually exhausted the population.

#### 2026-07-17 composite-cursor checkpoint

The first two lossless pages now form a valid cumulative dry run:

```text
pages                         2
revision-pinned statements   400
dependency groups             28
candidate-rule matches         4
no current rule              115
incomplete detector coverage 281
population exhausted       false
```

All four A1/A2 matches come from the single already reviewed Q101416961 family:
three A2 scoped components and one A1 total. They are candidate-rule matches,
not approved rules or migrations. The 281 incomplete rows expose the same
specific missing evidence: A3 cannot yet prove whole-family period partition
and independent member conformance. The 115 no-rule rows failed current
contracts rather than being forced into a similarity bucket. The cumulative
artifact is `/tmp/nat-contract-composite-cumulative-400.json`.

The earlier QID-only page-2 experiment remains a bounded sample only. It is not
part of the cumulative artifact because QID-only pagination cannot prove that
the prior entity's remaining GUIDs were not skipped.

#### Coverage-reduction order

The first two pages make evidence acquisition, rather than new rule invention,
the immediate constraint. `incomplete_coverage` must therefore carry a
reason-code and evidence-kind histogram. It distinguishes recoverable retrieval
gaps, bounded-inspection/closure limits, genuinely absent or ambiguous source
data, and missing policy evidence. Only the first two justify more retrieval;
the others remain a source or policy abstention.

The next generic carrier enhancement supplies a complete family with explicit
member evidence: normalized period values plus member conformance states. The
generic family carrier, not the Nat profile, determines whether periods are
distinct/non-overlapping and whether every supplied member is independently
conformant. The climate profile supplies only WD-normalized values and
target-model interpretation. This is required before `A3` can match; a partial
sibling set, unresolved member, duplicated annual period, or overlap remains an
abstention or hold.

Before adding overload (`B1`) or repair (`C1`) rules, complete rows should also
be assigned explicit target-domain exclusions where justified: a different
subject domain, incompatible quantity/method semantics, or a pre-existing
target-property collision. Exclusions are successful negative findings, not
failed migration rules. They remain distinct from true semantic holds such as
period/scope overlap, contradictory totals, and malformed statement families.

#### Family-geometry inventory before further rule expansion

The hydrated 400-row prefix closes a different question from rule
applicability:

```text
Do we have enough supplied, pinned evidence to assess the selected row?
→ yes for all 400 rows in the current prefix

Does the assessed row satisfy A1/A2/A3?
→ only four candidate matches, all from one dependency group
```

The resulting 396 complete non-matches must not be read as 396 independent
failures. They arise from 28 statement families, and predicate reason counts
overlap across the members of each family. The next output is therefore a
generic dependency-group inventory. The shared coverage layer groups
profile-supplied, typed residual/action assessments by dependency group; the
profile supplies domain meanings, while the generic carrier preserves member
sets, primary and secondary obstructions, affected subsets, coverage, and
non-executing status.

For the climate profile, the initial family geometries are:

```text
F1 coherent atomic total/component family
F2 coherent multi-year annual series
F3 unresolved or non-annual period representation
F4 overlapping or non-partitioned scopes
F5 contradictory/non-reconciling totals
F6 mixed statement semantics within one source-property family
F7 otherwise conformant member blocked by a sibling dependency
F8 malformed or legacy reconstruction family
```

These are diagnostic family actions, not migration rules. They may overlap in
secondary evidence, but each profile assessment must name one deterministic
primary obstruction. In particular, `family_conflict` remains a gate, not a
final diagnosis.

Period evidence must be retained at a finer shape than the former broad
`annual_period_partition_unresolved` reason. The supplied profile may
distinguish single point-in-time years, same-year closed intervals, distinct
annual intervals, multi-year intervals, mixed representations, duplicate
annual periods, overlaps, absent periods, and unparsable periods. The generic
carrier only checks supplied member coverage and aggregates those normalized
shapes; it does not parse Wikidata time values or decide annuality.

Likewise, sibling dependency is not automatically family-wide failure. A
profile must distinguish an independently migratable atomic member, a member
blocked by a contradiction/overlap, a member requiring sibling exclusion, and
a family requiring reconstruction. This is the future policy boundary for
partial family migration; no such policy is authorized by the current
candidate rules.

#### 2026-07-17 first hydrated family inventory

The same two live composite pages were replayed after the inventory carrier was
introduced. The cumulative dry run remains a prefix, not exhaustion:

```text
revision-pinned statements  400
dependency groups            28
candidate matches             4 (one family, still candidate-only)
complete no-rule/hold rows  396
coverage abstentions          0
```

The 28 groups now have one profile-owned primary geometry each:

```text
F1 coherent atomic total/component family        1
F4 overlapping/non-partitioned scopes           16
F5 contradictory/non-reconciling totals         11
```

The reviewed `Q101416961|P5991` family is the F1 control: four 2024 members,
already-separated scopes, exact component-to-total reconciliation, and
`same_annual_period_component_partition`. Repeated same-year component values
in that geometry are not a period-overlap diagnosis. The remaining action
queue is 13 overloaded-source reviews, 3 scope-partition holds, and 11
total-reconciliation holds. These are diagnostic family actions only; they do
not approve A1/A2/A3, a split, an edit, or partial-family migration.

The next refinement is now evidence-led rather than count-led: inspect the 16
F4 families to distinguish a genuinely overloaded source GUID from a valid
already-separated component structure, then model F5 total reconciliation as
typed contradiction evidence. Continue only contiguous composite pages, with
the current artifact at `/tmp/nat-family-geometry-v2-cumulative-400.json`.

#### 2026-07-17 family-hydration checkpoint

The same two pages were rerun after the generic carrier received all sibling
member assessments from each already revision-pinned entity export. This did
not make any new source request or grant a migration rule. It changed the
evidence boundary from “only selected WDQS rows were assessed” to “every
source-property sibling in the pinned entity family was assessed.”

```text
revision-pinned statements   400
dependency groups             28
candidate-rule matches         4
complete no-rule / hold      396
incomplete coverage            0
population exhausted       false
```

The four candidate matches remain the one Q101416961 dependency group. The
reduction from 281 abstentions to zero is therefore not an eligibility gain:
it proves that the previous incompleteness was recoverable family-hydration
incompleteness. The new generic report emits `no_rule_reason_counts` as the
deduplicated candidate/dependency-group work queue for the resulting complete
negative population. On this page pair, every complete negative row has
`family_conflict`; 383 also have an unresolved annual partition, 88 have an
unresolved or contradictory total relation, and 115 require another statement
disposition. Those counts overlap deliberately: they are residual evidence, not
a forced taxonomy. The next task is to classify them into explicit exclusions
versus typed overlap/contradiction/reconstruction holds, then expand the
lossless scan to a terminal short page. The current `company_direct` stratum
cannot itself exercise person/product exclusions by construction; those are
tested in generic/profile fixtures and require a later broader discovery
stratum for live counts.

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
