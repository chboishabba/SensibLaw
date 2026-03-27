# Wikidata Migration Pack Contract (2026-03-28)

## Purpose
Define the first executable contract for a bounded property-migration review
artifact in the Wikidata lane.

This contract is intentionally operational and narrow:
- one source property
- one target property
- one bounded slice
- one current window basis
- reviewer-facing candidate rows

The initial anchor case remains:
- source property: `P5991`
- target property: `P14143`

## Status
Implemented in bounded `v0.1` form through:
- schema:
  - `schemas/sl.wikidata_migration_pack.v1.schema.yaml`
- runtime:
  - `src/ontology/wikidata.py`
- CLI:
  - `sensiblaw wikidata build-migration-pack`

## Contract shape
Schema version:

```text
sl.wikidata_migration_pack.v1
```

Top-level fields:
- `schema_version`
- `source_property`
- `target_property`
- `window_basis`
- `source_slice`
- `candidates`
- `summary`

## Window basis
The pack is built from:
- current window = last window in the bounded slice
- previous window = second-to-last window when present

Current `v0.1` interpretation:
- review is centered on current-window source-property bundles
- previous-window state is used only for drift/comparison surfaces

## Candidate contract
Each candidate row represents one current-window source-property statement
bundle.

Required fields:
- `candidate_id`
- `entity_qid`
- `slot_id`
- `statement_index`
- `classification`
- `confidence`
- `requires_review`
- `reasons`
- `claim_bundle_before`
- `claim_bundle_after`
- `qualifier_diff`
- `reference_diff`

### `claim_bundle_before`
The normalized current source-property bundle:
- `subject`
- `property`
- `value`
- `rank`
- `qualifiers`
- `references`
- `window_id`

### `claim_bundle_after`
The proposed target-property bundle candidate:
- same bundle shape as `claim_bundle_before`
- property rewritten to the target property only

Interpretation:
- this is a candidate migration projection, not an edit command
- no claim is made that every candidate should be promoted

## Runtime classification buckets in `v0.1`
Implemented buckets:
- `safe_equivalent`
- `safe_with_reference_transfer`
- `qualifier_drift`
- `reference_drift`
- `ambiguous_semantics`
- `abstain`

Reserved / deferred buckets:
- `needs_human_review`
- `non_equivalent`
- `safe_add_target_keep_source_temporarily`
- `split_required`

Reason for the split:
- `v0.1` is an executable review artifact first
- richer semantic/policy lanes still need more explicit repo-local rules

## Classification rules in `v0.1`
The initial runtime policy is intentionally conservative.

Promotion-adjacent safe buckets:
- `safe_equivalent`
  - current bundle is evidence-bearing
  - no slot-level qualifier drift across the comparison window
  - no slot-level reference drift across the comparison window
  - no multi-value ambiguity in the current slot
  - current bundle has no references to transfer
- `safe_with_reference_transfer`
  - same as above, but the current bundle carries references

Reviewer buckets:
- `qualifier_drift`
  - slot-level qualifier signatures or qualifier property sets changed across
    the comparison window
- `reference_drift`
  - slot-level reference signatures or reference property sets changed across
    the comparison window
- `ambiguous_semantics`
  - current slot has more than one distinct value
- `abstain`
  - evidence gate not met in the current slot

## Drift surfaces
`v0.1` surfaces two normalized drift summaries per candidate:

### `qualifier_diff`
- `status`
- `from_window`
- `to_window`
- `severity`
- `qualifier_property_set_t1`
- `qualifier_property_set_t2`
- `qualifier_signatures_t1`
- `qualifier_signatures_t2`

### `reference_diff`
- `status`
- `from_window`
- `to_window`
- `severity`
- `reference_property_set_t1`
- `reference_property_set_t2`
- `reference_signatures_t1`
- `reference_signatures_t2`

## Summary contract
Required fields:
- `candidate_count`
- `counts_by_bucket`
- `checked_safe_subset`
- `abstained`
- `ambiguous`
- `requires_review_count`

Interpretation:
- `checked_safe_subset` is the bounded subset eligible for later export work
- the pack remains a review artifact until a later lane adds explicit export
  and post-edit verification

## CLI contract
Build a pack from a bounded slice:

```bash
sensiblaw wikidata build-migration-pack \
  --input path/to/slice.json \
  --source-property P5991 \
  --target-property P14143 \
  --output path/to/migration_pack.json
```

Current CLI output summary fields:
- `output`
- `schema_version`
- `candidate_count`
- `checked_safe_subset_count`
- `requires_review_count`

## Non-goals
- no direct bot or QuickStatements emission
- no claim of semantic non-equivalence beyond the implemented buckets
- no automatic use of WikiProject consensus as promotion truth
- no post-edit verification in `v0.1`

## Immediate followthrough after `v0.1`
1. Add richer reference-transfer diagnostics.
2. Add policy-driven `needs_human_review` / `non_equivalent` lanes.
3. DONE: pin one real climate migration pack in-repo.
   - materializer:
     `SensibLaw/scripts/materialize_wikidata_migration_pack.py`
   - artifact root:
     `SensibLaw/data/ontology/wikidata_migration_packs/p5991_p14143_climate_pilot_20260328/`
   - stored together:
     - raw revision-locked entity exports
     - bounded slice JSON
     - derived migration pack JSON
     - manifest / artifact note
4. Add checked-safe export and post-edit verification only after that pinned
   pack exists.
