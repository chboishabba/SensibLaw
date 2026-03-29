# BoundaryArtifact and Morphism Contract (2026-03-28)

## Purpose
Define the next higher formalism above the existing boundary-object work:

- `SourceUnit`
- `SplitPlan`
- `ClaimPair` / affidavit comparison artifacts
- `AffectSignal` / candidate affect overlays

The point is not a new runtime refactor yet.
The point is to make the transformation layer explicit:

> typed boundary artifacts + governed morphisms + composition rules

## Motivation
The repo now has multiple bounded lanes that share the same deep pattern:

1. force an ambiguous or risky input into a typed, provenance-bearing artifact
2. apply a bounded transformation
3. require review / abstention / promotion gating before stronger commitment

The current boundary artifacts are already real enough that "one more shared
interface" is no longer the interesting abstraction.

The next missing primitive is:

```text
Artifact --(governed transform)--> Artifact
```

## BoundaryArtifact
`BoundaryArtifact` is the shared conceptual supertype for typed,
provenance-bearing boundary objects.

Current repo examples:
- `SourceUnit`
- `SplitPlan`
- `EventCandidate`
- affidavit comparison / review candidates
- `AffectSignal`-like overlay candidates

Shared invariant:

> every downstream transformation must start from a typed, reviewable,
> provenance-preserving boundary artifact

## Morphism
`Morphism` is the governed transformation relation between boundary artifacts.

Minimal conceptual shape:
- `morphism_name`
- `input_type`
- `output_type`
- `constraints`
- `effect_kind`
- `review_requirement`
- `provenance_rule`

Examples:
- `capture : external_source -> SourceUnit`
- `extract : SourceUnit -> ObservationClaimPayload`
- `split : MigrationCandidate -> SplitPlan`
- `align : ClaimA x ClaimB -> ClaimPair`
- `promote : CandidateArtifact -> CanonicalArtifact`

Candidate future schema name:

```text
sl.morphism.v1
```

Minimal proposed fields:
- `morphism_id`
- `name`
- `input_types`
- `output_type`
- `semantics`
- `governance`
- optional `composition`
- optional `examples`

Candidate semantic fields:
- `determinism = deterministic | heuristic | mixed`
- `totality = total | partial | abstaining`
- `authority_level = signal | candidate | reviewed | promoted`
- `preserves_provenance`
- `lossiness = lossless | lossy | unknown`

## Effect semantics
Morphisms should be first-class about how they behave.

Important effect kinds:
- `deterministic`
- `partial`
- `guarded`
- `abstaining`
- `heuristic`

This matters because the repo already relies on:
- abstention
- guarded promotion
- review-only artifacts
- bounded heuristics

## Composition rules
The real structure is not just "what artifacts exist."
It is "which transformations are allowed to compose."

Examples:
- `capture -> extract -> align -> propose` is valid
- `affect_overlay -> promote_truth` is not automatically valid
- `split -> execute` must remain blocked without explicit verification policy

So the next formalism is not just a data contract.
It is a typed composition system over transforms.

Candidate executable followthrough if runtime pressure later justifies it:
- a bounded `Morphism.v1` schema
- a minimal composition validator
- an intentionally small DSL for readable transformation chains

Illustrative valid chains:
- `capture_source_unit -> extract_observation`
- `source_row -> propose_split_plan -> review -> verify`

Illustrative invalid chain:
- `AffectSignal -> affect_to_tag -> promote_legal`

Reason:
- signal-layer outputs must not directly compose into promoted legal outputs
  without an intervening governed candidate/review layer

## Governance
Global rule:

> No transformation may bypass the boundary-artifact layer.

Corollaries:
- raw source should not flow straight to promoted truth
- format-specific ingest paths must normalize into typed source artifacts first
- proposal/execution review boundaries must remain explicit
- no morphism may silently discard provenance

## Current decision
Do not implement a shared runtime transformation algebra yet.

Reason:
- the repo has enough concrete boundary objects to justify the concept
- but not yet enough repeated runtime pressure to justify a unifying engine
- docs-first is sufficient to guide the next few implementations

## Immediate followthrough
1. Treat `SourceUnit`, `SplitPlan`, `EventCandidate`, and affect/coverage
   overlays as the first explicit boundary-artifact family.
2. Keep new runtime work typed around artifact boundaries rather than
   format- or lane-specific shortcuts.
3. If a shared runtime is later justified, define:
   - `BoundaryArtifact.v1`
   - `Morphism.v1`
   - a bounded composition validator
   - a small readable DSL for allowed transformation chains
4. Until then, use this note as the policy surface:
   composition rules are real, but runtime unification remains deferred.
