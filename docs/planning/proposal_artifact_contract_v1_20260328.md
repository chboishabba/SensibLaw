# ProposalArtifact Contract v1 (2026-03-28)

## Purpose
Define the first shared review/proposal artifact above domain-specific
transformation lanes such as Wikidata `SplitPlan` and fact-intake
`EventCandidate`.

This note is intentionally narrower than the later
`boundary_artifact_morphism_contract_20260328.md` note:
- this file is about shared proposal/review artifacts
- the later note is about typed transformations over boundary artifacts more
  generally

This note is intentionally contract-first:
- no runtime refactor yet
- no forced cross-domain implementation in one step
- use current bounded artifacts as proving grounds

## Motivation
Several lanes now share the same structural pattern:
- detect a non-promotable or ambiguous source state
- preserve evidence/provenance
- emit a reviewable proposal artifact
- require review before promotion or execution

Current examples:
- Wikidata property migration:
  - `MigrationPack`
  - `SplitPlan`
- fact-intake / timeline lanes:
  - `EventCandidate`
- affidavit / contradiction lanes:
  - affidavit proposition review rows
  - contradiction-resolution candidates
- affect / sentiment / utterance lanes:
  - candidate interpretation overlays

The common missing primitive is not "execution".
It is a shared, reviewable proposal layer.

## Contract shape
Schema name proposed for future implementation:

```text
sl.proposal_artifact.v1
```

Minimal shared fields:
- `artifact_id`
- `artifact_type`
- `source_id`
- `transformation_type`
- `targets`
- `evidence`
- `constraints`
- `review_status`
- `suggested_action`
- `verification_requirements`

## Field interpretation

### `artifact_id`
Stable id for the proposal artifact itself.

### `artifact_type`
Domain-specific subtype, for example:
- `split_plan`
- `event_candidate`
- `legal_candidate`
- `affect_candidate`

### `source_id`
Stable ref to the source state being transformed.

Examples:
- Wikidata slot id / candidate ids
- affidavit claim id
- utterance id

### `transformation_type`
The kind of move being proposed, for example:
- `one_to_one_migration`
- `one_to_many_split`
- `candidate_interpretation`
- `conflict_resolution`

### `targets`
The proposed target states or target bundles.

Interpretation:
- proposal artifacts may have zero, one, or many targets
- `one -> many` is first-class, not exceptional

### `evidence`
Bounded evidence supporting the proposal.

Examples:
- split axes
- source statement bundles
- text observations
- contradiction edges

### `constraints`
The explicit safety/governance constraints attached to the proposal.

Examples:
- no invented values
- exact reference propagation only
- review required before execution

### `review_status`
Proposal state, for example:
- `draft`
- `review_required`
- `reviewed`
- `verified`
- `rejected`

### `suggested_action`
What the operator should do next.

Examples:
- `review_structured_split`
- `review_only`
- `migrate`
- `abstain`

### `verification_requirements`
What must be checked after promotion/execution.

Examples:
- exact target presence
- qualifier preservation
- reference preservation
- source retirement or source coexistence check

## Current subtype mapping

### `MigrationPack`
Current role:
- bounded classification/proposal surface over source rows

Maps to `ProposalArtifact` as:
- `artifact_type = migration_candidate`
- usually `transformation_type = one_to_one_migration`
- may downgrade into `split_required` instead of direct promotion

### `SplitPlan`
Current role:
- first concrete `one -> many` review artifact

Maps to `ProposalArtifact` as:
- `artifact_type = split_plan`
- `transformation_type = one_to_many_split`
- `targets = proposed_target_bundles`
- `evidence = merged_split_axes + source_candidate_ids`
- `constraints = no invented values, review-only, propagation policy`

### `EventCandidate`
Current role:
- deterministic proposal artifact between raw observation intake and promoted
  event/claim surfaces

Maps to `ProposalArtifact` as:
- `artifact_type = event_candidate`
- `transformation_type = candidate_interpretation`
- `targets = proposed event rows / downstream claim-ready event state`
- `evidence = source observations + attribution / provenance links`
- `constraints = reconstructable from observations, bounded derivation rules,
  review before stronger promotion`

### `AffidavitCoverageReview`
Current role:
- review artifact for comparing affidavit-side propositions against a
  provenance-bearing source slice

Maps to `ProposalArtifact` as:
- `artifact_type = affidavit_review_candidate`
- `transformation_type = coverage_review`
- `targets = reviewed affidavit proposition statuses / source-side omission
  statuses`
- `evidence = affidavit propositions + source-grounded rows + excerpts`
- `constraints = no affidavit wording replaces source structure, unsupported
  propositions remain explicit`

## Governance
Global invariant:

> No `1 -> N` transformation should occur without an explicit, reviewable
> proposal artifact.

Corollaries:
- detection alone is insufficient for execution
- review-only artifacts are valid terminal states
- abstention is preferable to invented decomposition
- execution should always trail proposal and verification

## Current decision
Do not refactor current runtimes to a shared base type yet.

Reason:
- `SplitPlan` and `EventCandidate` already give two concrete mapped subtypes
- the affidavit review lane provides a third cross-checking review surface
- the remaining question is shared runtime value, not lack of proving grounds
- docs-first keeps the architecture coherent without destabilizing working code
- if the repo later needs a higher shared formalism, treat
  `ProposalArtifact` as one boundary-artifact family within the broader
  boundary-artifact + morphism system, not as the only shared abstraction

## Immediate followthrough
1. Treat `SplitPlan` and `EventCandidate` as the first two explicit
   `ProposalArtifact` mappings already present in the repo.
2. Use the affidavit coverage/review lane as the cross-domain stress test for
   whether the shared contract is actually stable.
3. Before any shared runtime/schema refactor, add a short explicit field-level
   mapping note from the existing `EventCandidate` contract into
   `ProposalArtifact v1`.
