# Climate-GHG Orthogonal Assessment V2

Date: 2026-07-17

Status: canonical derived-assessment contract

## Purpose and authority

This contract defines a deterministic, offline V2 assessment over a pinned
Wikidata migration-pack replay. It separates five questions that legacy
A1-A5/H4 labels combine: family geometry, semantic-slot integrity, component
coverage, statement semantics, and candidate eligibility.

The assessment is diagnostic and read-only. `eligible` means only that a
statement may enter candidate review. It never grants promotion, edit,
execution, source-quality, or community-approval authority. Reference
adequacy in v0.1 means that a non-empty transferable reference structure is
present; it is not an endorsement of the source.

The pinned 2026-07-17 company-direct replay is immutable input. Its migration
pack, manifest, slice, run state, rule coverage, and H4 collision report must
not be rewritten. V2 artifacts live below `derived/orthogonal_v2/`.

## Ownership boundary

Shared policy code owns a vocabulary-neutral orthogonal carrier and report
builder. It validates axis cardinality, family and statement references,
stable ordering, provenance hashes, authority boundaries, outcome invariants,
and aggregate counts. It must not know climate QIDs or A/H labels.

`src/policy/climate_ghg_transformation_profile.py` owns climate policy:
coordinate derivation, known GHG QID mappings, geometry and semantic subtypes,
coverage rules, eligibility predicates, and legacy A1-A5/H4 projections.

The offline command reads only local replay artifacts. No Wikidata request,
edit manifest, migration proposal, or write-capable artifact is permitted.

## Carrier axes

Every source family has exactly one family assessment. Every source statement
has exactly one statement assessment, refers to its family, and has exactly
one value on every axis.

### Family geometry

Precedence is `atomic`, `annual_series`, `multidimensional_matrix`, then
`unresolved`:

- one member is atomic;
- multiple exact years with otherwise invariant semantics form an annual
  series;
- total/components or variation in scope, category, method, or unit form a
  multidimensional matrix;
- remaining shapes are unresolved.

Matrix bases are `year_scope`, `year_scope_category`, `total_scope`,
`total_scope_category`, `other`, or `unresolved`. Series bases are
`total_series`, `scoped_component_series`, `category_series`, or
`irregular_year_series`. Non-exclusive flags are `method_variant`,
`unit_variant`, `reference_variant`, `mixed_rank_or_revisioned`, and, where
applicable, `unresolved_temporal`.

### Slot integrity

Year, scope, category, method, and unit each carry an identity state. Exact or
non-applicable coordinates plus a unique semantic slot are `coherent`.
Confirmed same-slot duplicates, conflicting values, or rank/supersession
collisions are `collided`. Identity dependent on missing, fiscal-canonical, or
ambiguous coordinates is `unresolved`.

H4a-H4d remain compatibility projections. H4b includes actionable coordinate
reasons drawn from year, scope, category, method, unit, and reference basis.

### Component coverage

- `exhaustive`: exact total/component reconciliation on a comparable basis;
- `partial`: established nonexhaustiveness, including selected components,
  selected Scope 3 categories, or components exceeding the total without
  exhaustiveness evidence;
- `unknown`: boundary-incomparable, numerically unavailable, or unresolved;
- `not_applicable`: no meaningful total/component comparison.

A5 projects only from `partial`. `unknown` remains a separate diagnostic and
neither coverage state independently authorizes nor blocks a statement.

### Statement semantics

A1 total subtypes are `organisation_wide_total` and
`unresolved_total_basis`. A2 component subtypes are `scope_1`,
`scope_2_aggregate`, `scope_2_location`, `scope_2_market`,
`scope_3_aggregate`, `scope_3_named_category`, `other_explicit_component`,
and `unresolved`. Complete but unsupported shapes are `unsupported`; missing
or ambiguous semantic evidence is `unresolved`.

### Eligibility predicates and outcomes

The following three-valued predicates are evaluated independently:
`enterprise_subject`, `exact_annual_period`, `target_semantics_fit`,
`supported_statement_shape`, `compatible_method`, `compatible_unit`,
`structurally_adequate_reference`, `unique_semantic_slot`, and
`no_target_collision`.

Outcome precedence is:

1. confirmed slot or target collision: `hold`;
2. any required unresolved evidence: `hold`;
3. all predicates true: `eligible`;
4. otherwise complete but unsupported evidence: `no_rule`.

An eligible statement cannot coexist with H4 or a collision. Partial coverage
does not enter this outcome precedence by itself.

## Compatibility projections

- A1/A2 derive from statement semantics and are mutually exclusive.
- A3/A4 derive from family geometry plus coherent integrity and are mutually
  exclusive.
- A5 derives only from partial component coverage and may coexist with the
  contextual projections above.
- H4 derives from collided or unresolved slot integrity and never coexists

## Evidence and governance tranche

The next tranche extends V2 with derived-only evidence reports over the same
immutable replay. It does not change the classifier, replay payloads, or
authority boundary.

- The existing deterministic 15-family manifest is the review population.
- Human adjudication is recorded in a versioned JSON sidecar tied to the V2
  assessment and source provenance hashes. CSV/OpenRefine export is deferred.
- Reports distinguish an exclusive primary hold reason from all overlapping
  reasons. Primary precedence is semantic-slot identity, enterprise-subject
  evidence, reference adequacy, annual-period evidence, target semantics, then
  other unsupported/incompatible predicates.
- Unknown component coverage is subdivided into missing totals, unrecognised
  partitions, incomparable boundaries, absent exhaustiveness evidence,
  unresolved boundaries, and unavailable arithmetic evidence where supported by
  the replay evidence.
- A4 strict-detector attrition lists each lost family, failed or unresolved
  predicate, member count, and V2 outcome counts.
- A semantic subtype can propose a governed candidate contract only with at
  least five reviewed eligible statements, at least 95% eligible precision, and
  no critical target, qualifier, or collision miss. The largest qualifying
  subtype wins; ties prefer organisation-wide totals, then Scope 1, Scope 2,
  Scope 3 aggregate, and named Scope 3 category.
- A qualifying contract emits a read-only, deterministically selected canary of
  at most 25 statements. It remains a review manifest, never an edit or
  execution manifest.

The next narrower tranche is specified in
`docs/planning/climate_ghg_policy_resolution_dry_run_20260717.md`. It tests
132 fiscal-year-only holds, 21 Q52579 subject holds, 4 Q1476113 reference
holds, and concentrated method/unit cases (12/3) without bundling the 176
fiscal-plus-ambiguous-scope statements into the fiscal policy.
  with `eligible`.

Legacy behavior and artifacts remain unchanged. The comparison artifact must
show legacy primary assessment, strict detector matches, V2 projections, and
predicate-level attrition, including the pinned reconciliation values:

- legacy A4: 124 families / 2,416 statements; strict A4: 110 / 2,198;
- legacy A5: 90 families / 830 statements; strict A5: zero;
- H4: 5 families / 25 collision groups / 50 direct members; strict H4:
  2 groups / 15 matches.

The 14-family / 218-statement A4 difference must be explicitly attributed.

## Offline materialization

`scripts/materialize_climate_ghg_orthogonal_assessment.py` accepts
`--replay-dir`, optional `--output-dir`, `--sample-family-limit` (default 15),
and the shared terminal progress formats. It verifies exhausted population,
revision/manifest consistency, family and statement population equality, and
per-statement target-collision evidence.

SHA-256 provenance is recorded for `run-state.json`, `manifest.json`,
`slice.json`, `migration_pack.json`, `rule_coverage.json`, and
`h4_collision_report.json`.

The command stages and fsyncs the full artifact set before atomically
installing the output directory. A byte-identical existing directory succeeds
without rewriting. A differing existing directory fails and requires a new
output directory.

The output set is:

- `orthogonal_assessment.json`, schema `sl.climate_ghg_assessment.v2`,
  classifier `climate-ghg-orthogonal-assessment-v0_1`;
- `orthogonal_coverage_report.json` with family/statement axis, subtype,
  intersection, and outcome counts;
- `legacy_projection_comparison.json` with compatibility reconciliation and
  predicate attrition;
- `eligibility_review_manifest.json`, a read-only sample containing every
  statement in 15 deterministically selected families and four reviewer
  questions.

Review-family selection uses deterministic greedy coverage across outcome,
geometry subtype, coverage subtype, size bucket, annuality, rank/reference
variation, and total/scope/category shape, with family-reference tie-breaking.

## Acceptance

The pinned run must emit 232 family records and 3,562 statement records. Axis
and outcome counts must sum to their respective populations, references must
be closed and deterministic, and source provenance hashes must verify.

Tests cover generic validation and ordering; all climate geometry, coverage,
semantic, H4-coordinate, compatibility, and three-valued outcome branches;
offline interrupted staging and existing-output behavior; input mismatch; and
absent, present, and unresolved target-collision evidence. Focused tests, the
existing climate/materializer regressions, Ruff check, and Ruff format check
are required before this contract is considered implemented.
