# Wikidata Split Plan Contract (2026-03-28)

## Purpose
Define the first bounded `1 -> N` review artifact for `split_required`
migration rows.

This is now also one concrete subtype of the broader docs-first
`ProposalArtifact v1` contract in:
- `docs/planning/proposal_artifact_contract_v1_20260328.md`

This contract is intentionally narrow:
- input is an existing `MigrationPack`
- only `split_required` rows are considered
- output is review-only
- no direct edit payloads are emitted

## Status
Implemented in bounded `v0.1` form through:
- schema:
  - `schemas/sl.wikidata_split_plan.v0_1.schema.yaml`
- runtime:
  - `src/ontology/wikidata.py`
- CLI:
  - `sensiblaw wikidata build-split-plan`

## Contract shape
Schema version:

```text
sl.wikidata_split_plan.v0_1
```

Top-level fields:
- `schema_version`
- `source_property`
- `target_property`
- `plans`
- `summary`

## Plan contract
Each plan groups all `split_required` candidates for one source slot.

Required fields:
- `split_plan_id`
- `entity_qid`
- `source_slot_id`
- `source_candidate_ids`
- `status`
- `review_required`
- `merged_split_axes`
- `proposed_target_bundles`
- `proposed_bundle_count`
- `reference_propagation`
- `qualifier_propagation`
- `suggested_action`

## Current statuses
- `structurally_decomposable`
  - every source candidate in the slot is already a `split` action
  - the proposed target bundles are distinct
  - the slot yields at least two target bundles
  - split axes are present
- `review_only`
  - the slot is still split-required, but the current structure is not strong
    enough for a clean structural fanout plan

## Current runtime policy
The first implementation only proposes decompositions when the structure is
already present in the migration pack.

That means:
- no invented values
- no inferred missing years/scopes from nothing
- no source-text-driven fanout here
- no automatic edits

Current construction rule:
- group `split_required` candidates by `slot_id`
- merge their `split_axes`
- reuse each candidate's `claim_bundle_after` as a proposed target bundle
- keep the plan review-only even when it is structurally decomposable

## Propagation surfaces
The contract records whether qualifier/reference propagation appears exact or
still needs review:
- `reference_propagation`
  - `exact`
  - `review_required`
- `qualifier_propagation`
  - `exact`
  - `review_required`

## CLI contract

```bash
sensiblaw wikidata build-split-plan \
  --input path/to/migration_pack.json \
  --output path/to/split_plan.json
```

CLI summary fields:
- `output`
- `schema_version`
- `plan_count`
- `counts_by_status`

## Non-goals
- no direct edit payloads
- no decomposition of rows lacking structural fanout evidence
- no text-based split inference in `v0.1`
- no verification of split execution yet

## Immediate followthrough
1. Keep `SplitPlan` review-only until a separate split verification contract
   exists.
2. If text evidence is later used for decomposition, keep it additive and
   bounded behind the existing `Phi` bridge rules.
3. Only consider execution/export after one real split plan has been reviewed
   and validated against an after-state.
4. Use this artifact together with `EventCandidate` and the affidavit review
   lane as the proving ground set for the broader `ProposalArtifact v1`
   abstraction before any shared runtime refactor.
