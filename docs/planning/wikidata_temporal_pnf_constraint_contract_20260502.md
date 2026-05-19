# Wikidata Temporal PNF Constraint Contract

Date: 2026-05-02
Status: planning contract, not runtime behavior

## Purpose

Define the shared predicate-normal-form read for two Wikidata ontology review
families that previously looked separate:

- temporal/multi-value climate statements such as `P5991 -> P14143`
- temporally bounded mereology/parthood statements such as `P361`

The common structure is a statement family whose temporal requirement is
currently implicit in observed statement shape, not declared as a complete
`P2302` constraint surface. The contract below names that implicit requirement
as a PNF/residual precondition so later implementation can test it without
changing the existing promotion gate or A/B/C/D/E routing vocabulary.

## Formal Model

O:
- Decision surface: SensibLaw/ITIR Wikidata control-plane docs and future
  runtime helpers.
- Review audience: OCTF / ontology reviewers working across climate migration
  and mereology/parthood lanes.

R:
- A proposed Wikidata add/change must preserve temporal completeness whenever
  the local item/property slice is already temporally bounded.
- A proposed add/change must also avoid overlap contradictions for property
  families that are exclusive under a temporal key.

C:
- Existing related docs:
  - `SensibLaw/docs/planning/wikidata_pnf_residual_review_example_20260429.md`
  - `SensibLaw/docs/planning/wikidata_mereology_parthood_note_20260307.md`
  - `SensibLaw/docs/planning/wikidata_climate_change_property_migration_protocol_20260327.md`
  - `SensibLaw/src/text/residual_lattice.py`
- Proposed later runtime surface:
  - ontology index / slice-build helper that computes temporal family state
  - residual precondition in the Wikidata candidate evaluator

S:
- Climate review already has temporal/multi-value split pressure.
- Parthood review already has typed parthood and inverse-validity pressure.
- The shared temporal-completeness rule is not yet a named runtime primitive.

L:
- `candidate-only`: raw temporal or parthood signal exists.
- `reviewable`: bounded slice exposes statement family, temporal qualifiers,
  and overlap evidence.
- `held`: temporal completeness or overlap evidence is incomplete or risky.
- `promotable`: the candidate satisfies temporal preconditions and any
  family-specific residual checks.

P:
- Represent temporal completeness as a PNF/residual precondition, not as a
  hidden edit heuristic.
- Keep climate and mereology on the same residual skeleton, with different
  property-family policies.

G:
- This document does not authorize automated edits, rejection, or reverts.
- Runtime support requires fixture-backed tests for both climate and mereology
  examples before any promotion claim.
- Missing temporal qualifiers must remain distinguishable from missing `P2302`
  signature qualifiers.

F:
- No implementation currently computes `TempFam(P, I)` as a reusable index.
- No fixture currently proves the unified climate + mereology residual path.
- The exclusive-property set needs curator review before runtime use.

## PNF Interpretation

A candidate statement add is normalized as:

```text
delta = add(P, v, Q) on item I
S(I) = existing bounded statement slice for I
```

The statement itself becomes a `PredicatePNF`-compatible carrier:

```text
predicate: wikidata_statement_add
roles:
  item: I
  property: P
  value: v
qualifiers:
  wikidata_qualifiers: Q
wrapper:
  evidence_only: true
  status: candidate
```

The temporal constraint is a second carrier:

```text
predicate: temporal_completeness_constraint
roles:
  item: I
  property: P
  temporal_key_set: {P580, P582, P585}
wrapper:
  evidence_only: true
  status: constraint_candidate
```

The residual evaluator reads these carriers before ordinary structural checks.

## Temporal Family Index

Define `TempFam(P, I)` from the bounded slice at slice-build time:

```text
TempFam(P, I) = true
  iff there exists s in S(I) where
    s.P = P
    and qualifiers(s) intersects {P580, P582, P585}
```

If `TempFam(P, I)` is false, the temporal precondition passes.

If `TempFam(P, I)` is true, every new statement on the same item/property must
carry at least one member of the temporal key set:

```text
TemporalComplete(delta, S) =
  true  if TempFam(P, I) = false
  true  if TempFam(P, I) = true
        and Q intersects {P580, P582, P585}
  false otherwise
```

The failure residual is:

```text
INCOMPLETE_tau
reason: missing_temporal_qualifier
```

This is intentionally separate from:

```text
INCOMPLETE_sigma
reason: missing_required_signature_qualifier
```

The first is inferred from local temporal-family shape. The second is inferred
from an explicit signature or property-constraint requirement.

## Overlap Policy

Temporal completeness is necessary but not sufficient for exclusive families.

Represent each statement interval as:

```text
Interval(s) = [start(s), end(s)]
start(s) = P580 if present else -infinity
end(s) = P582 if present else +infinity
```

For point-in-time families, use the point as a degenerate interval:

```text
Interval(s) = [P585, P585]
```

Two intervals overlap when:

```text
Overlap([a1, b1], [a2, b2]) = a1 <= b2 and a2 <= b1
```

Define an exclusive temporal family as a curated policy surface. In the
mereology-facing notation this is `MereExcl(P)`; in the more general
climate/measurement notation it can be read as `TemporalExcl(P)`.

```text
MereExcl(P) = true for curated properties where two different values
cannot safely coexist for the same item and overlapping temporal key.
```

Initial candidate families:

- mereology/location-like:
  - `P361` (`part of`)
  - `P17` (`country`)
  - `P131` (`located in administrative territorial entity`)
  - `P495` (`country of origin`) and `P571` (`inception`) are candidate
    pressure-test members only, pending curator review of whether they really
    behave as exclusive temporal families in the target slice.
- climate quantity-like:
  - `P14143` (`annual greenhouse gas emissions`) using `P585`
  - selected `P5991` rows only when the migration lane has classified them as
    annual organization-level emissions

Non-exclusive family:

- `P527` (`has part`) is not exclusive by default. A whole can have many parts
  at the same time.

The overlap violation is:

```text
TemporalOverlapViol(delta, S) =
  MereExcl(P)
  and exists s in S(I):
    s.P = P
    and s.value != v
    and Overlap(delta, s)
```

The contradiction residual is:

```text
CONTRADICTION_mu
reason: temporal_exclusive_overlap
evidence:
  conflicting_statement: s
  overlapping_interval: Interval(delta) intersect Interval(s)
```

`CONTRADICTION_mu` is named for the shared mereology/measurement-style
exclusivity shape. It should not imply that every climate row is literally a
parthood claim.

## Residual Function

The extended residual function is:

```text
R(delta, S) =
  INCOMPLETE_tau
    if TemporalComplete(delta, S) = false

  CONTRADICTION_mu
    if TemporalComplete(delta, S) = true
    and TemporalOverlapViol(delta, S) = true

  eval_C(S + delta)
    otherwise
```

This is a precondition layer over existing structural evaluation. It does not
replace the current climate migration buckets or parthood diagnostics.

## Climate Substitution

For the climate migration lane:

```text
P = P14143
temporal key = P585
exclusive key = one annual value per item/year/scope/method family
```

A candidate `P14143` statement without `P585` fails as:

```text
INCOMPLETE_tau / missing_temporal_qualifier
```

A candidate `P14143` statement for the same item and year as an existing
different value fails as:

```text
CONTRADICTION_mu / temporal_exclusive_overlap
```

Scope and method qualifiers still matter. A later runtime must not collapse
distinct scope/method families into a false duplicate-year contradiction.

## Mereology Substitution

For the mereology lane:

```text
P = P361
temporal keys = P580, P582, or P585
exclusive key = one whole per item/interval for curated exclusive properties
```

A proposed `P361` statement without temporal qualifiers fails only when the
same item/property slice is already temporally bounded.

A proposed `P361` statement pointing to a different whole over an overlapping
interval fails as:

```text
CONTRADICTION_mu / temporal_exclusive_overlap
```

`P527` remains outside the default exclusivity set.

## Implementation Boundary

Later implementation should add three small surfaces:

1. `TempFam(P, I)` computed during slice build.
2. A curated `MereExcl` / temporal-exclusivity policy table, separated from raw
   Wikidata truth.
3. A deterministic interval-overlap helper that supports open bounds and
   point-in-time degenerate intervals.

The first executable slice should be fixture-backed and should include:

- one climate case with `P14143` / `P585` duplicate-year pressure
- one mereology case with `P361` / `P580` / `P582` overlap pressure
- one non-exclusive `P527` control case
- one `INCOMPLETE_tau` case where temporal qualifiers are missing after the
  local property family has become temporally bounded

No promotion gate changes are required. The residual output should feed the
existing review buckets.

## ChangeReviewPacket Representation

The review-only packet lane reserves two first-class check-family names:

- `mereology`
- `temporal_exclusivity`

Packets may include a packet-local `check_family_policy` that names the bounded
property set, temporal key properties, and filter-respecting monotonicity
assumption. The runtime-facing exclusivity list is
`temporal_exclusivity_policy.exclusive_properties`; compatible whole pairs may
be supplied as review-only exceptions. These policy fields are descriptive
review input only. They are not live Wikidata authority, do not create PNF
receipts, and must not use label text as inspection evidence.

The current executable fixture is
`tests/fixtures/wikidata/change_review_mereology_temporal_packet.json`.
`compare-candidates` reports these families as run when the packet's property
scope includes the required parthood or temporal-exclusivity property family.
This is still a bounded review-only slice check, not a global ontology-index
claim or promotion receipt.

Abstract obligation candidate operations in `ChangeReviewPacket` are allowed
for review routing only: `split_class_obligation`, `new_class_obligation`,
`new_property_obligation`, `relation_family_correction`,
`upstream_repair_obligation`, and `sibling_normalization_obligation`. They are
existential review objects rather than Wikidata QIDs/PIDs or edit authority.
They may preserve pressure that cannot honestly collapse to a concrete bounded
statement mutation inside the packet.
