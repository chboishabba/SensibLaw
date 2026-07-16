# Wikidata Nat Cohort D Type-Probing Surface

Date: 2026-04-02

## Purpose

Turn Cohort D (subjects with no `instance of`) into a bounded type-probing
review artifact that remains fail-closed and non-executing.

This tranche extends the Cohort D review lane without changing cohort scope.

## Runtime Helper

- `SensibLaw/src/ontology/wikidata_nat_cohort_d_review.py`
- builder:
  `build_wikidata_nat_cohort_d_type_probing_surface(...)`

The builder projects:

- the Cohort D review surface fixture
- bounded reviewer packets for Cohort D probe rows

into one review-only type-probing artifact.

## Pinned Artifact

- `SensibLaw/tests/fixtures/wikidata/wikidata_nat_cohort_d_type_probing_surface_20260402.json`

Current bounded output:

- artifact status: `review_only_ready`
- probe rows: `2` (`Q738421`, `Q1785637`)
- unresolved packet refs: `0`
- governance: `automation_allowed=false`, `can_execute_edits=false`,
  `promotion_guard=hold`, `fail_closed=true`

## Non-Claims

- no direct migration execution
- no checked-safe promotion from missing `instance of` alone
- no cross-cohort expansion (B/C/E remain out of scope)

## Next Gate

- keep gate as `type_probing_scan_review_only`
- if packet refs are missing, artifact status must remain
  `review_only_incomplete` and surface unresolved refs explicitly

## Generic external-graph integration

The first slice-backed integration target is the existing `Q1785637` probe row.
It is not a Nat-owned resolver or type checker. The generic path is:

```text
Nat packet/source anchors
-> generic local entity candidate
-> revision-bound external graph plan with declared payload cost
-> selected graph coverage
-> external bridge proposal/review decision
-> generic property-presence or type-pressure diagnostic
-> review-only Cohort D packet projection
```

The graph view remains incomplete unless the stated query coverage is certified.
Consequently, a selected graph slice may confirm observed direct `P31`
evidence, and later traverse `P279` only when such a type is actually
observed; it cannot infer that no other typing statement exists outside its
coverage.
The diagnostic must therefore distinguish `observed_absence` from global
absence and return `abstain` or `warning` when coverage does not justify a
stronger conclusion.

The first profile checks only the explicitly named `P31` typing deficit. A
later company/organisation profile and other entity-kind profiles will reuse
the same generic expected-property carrier with different declared
expectations; they must not be encoded as Cohort-D or Nat primitives.

### 2026-07-16 checkpoint

The generic `build_expected_property_pressure(...)` evaluator now replays the
revision-pinned `Q1785637@2443793937` evidence named by the existing live
tranche fixture. The local entity, bridge proposal, accepted identity review,
graph view, pressure result, review projection, linkage case, and receipt are
all exercised through the provider-neutral carrier.

The result is deliberately `abstain`: the recorded observation is that `P31`
was absent in that bounded entity-export evidence, but the graph view is
incomplete. This is a deterministic regression proof, not a fresh network
query, current-state assertion, Zelph shard payload load, global absence claim,
or migration decision. The next transport adapter step is to ingest a freshly
fetched revision-pinned entity export or selected Zelph payload into the same
observation shape before rerunning the generic diagnostic.
