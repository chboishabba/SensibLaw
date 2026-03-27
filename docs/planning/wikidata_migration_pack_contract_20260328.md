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
- `action`
- `confidence`
- `requires_review`
- `reasons`
- `split_axes`
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
- `split_required`
- `abstain`

Reserved / deferred buckets:
- `needs_human_review`
- `non_equivalent`
- `safe_add_target_keep_source_temporarily`
- `ambiguous_semantics`

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
- `split_required`
  - current slot has more than one distinct value
  - or one statement carries multiple temporal values / a start-end range
  - or sibling statements show a temporal split that cannot be migrated 1:1
- `abstain`
  - evidence gate not met in the current slot

## Runtime action field in `v0.1`
Each candidate also carries a narrow machine action:
- `migrate`
- `migrate_with_refs`
- `split`
- `review`
- `abstain`

Interpretation:
- `action` is the runtime recommendation attached to the candidate row
- it remains a review aid, not an edit command
- `split` means the current `P5991` statement looks decomposable rather than
  safely movable 1:1

## Bridge-ready additive surface
The next executable bridge slice may add review metadata without changing the
structured baseline.

Planned additive fields:
- top-level `bridge_cases`
- candidate `text_evidence_refs`
- candidate `bridge_case_ref`
- candidate `pressure`
- candidate `pressure_confidence`
- candidate `pressure_summary`

Interpretation:
- these fields are additive review metadata only
- they do not change the rule that structured migration review is the baseline
- they become meaningful only when promoted text observations are present

## General split rule
`split_required` is now driven by a property-agnostic test:
- does the source statement bundle encode multiple independent axes of
  variation that cannot be represented as one target statement without loss?

Current runtime shape:
- `split_axes` is emitted per candidate
- each axis records:
  - `property`
  - `cardinality`
  - `source` (`bundle` or `slot`)
  - `reason`

Current interpretation:
- `__value__` is used as the pseudo-axis when the slot contains multiple
  distinct source values
- qualifier properties become axes when they vary across the bundle or its
  sibling statement context

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

Full-set interpretation:
- the current contract is already valid for full-set classification/filtering
- the current contract is not yet sufficient as a final migration-execution
  contract
- the main unresolved policy gap is now narrower:
  temporal/multi-value cases can graduate to `split_required`, but richer
  semantic buckets and post-edit verification are still missing

## OpenRefine bridge
The first operator-facing bridge should be review-first and flat-table shaped:

```text
SensibLaw MigrationPack -> OpenRefine CSV
```

The bridge does not emit Wikidata edits directly. It exports classified
candidate rows for OpenRefine faceting and review.

Recommended CSV columns:
- `candidate_id`
- `entity_qid`
- `slot_id`
- `statement_index`
- `from_property`
- `to_property`
- `value`
- `rank`
- `classification`
- `action`
- `confidence`
- `requires_review`
- `suggested_action`
- `split_axis_count`
- `split_axis_properties`
- `qualifier_drift`
- `reference_drift`
- `qualifier_diff_status`
- `reference_diff_status`
- `qualifier_diff_severity`
- `reference_diff_severity`
- `reference_count`
- `qualifier_count`
- `reason_codes`
- `notes`

Interpretation:
- OpenRefine is the human review / filtering surface
- SensibLaw remains the semantic classification layer
- edit execution stays out of scope for this bridge

Current operator claim:
- this bridge is strong enough for:
  - filtering a large/full candidate set
  - faceting obvious no-go cases
  - reviewing likely-safe subsets
- this bridge is not yet strong enough for:
  - fully trusted migration execution
  - final import payload generation for every row
  - precise machine action on all temporal/multi-value cases

Plain-language boundary:
- current checks are structured bundle checks, not source-text reading
- current output helps separate "probably safe" from "please review this"
- current output does not yet justify claiming that every row has a final
  machine action

## Checked-safe export
The first execution-adjacent export is deliberately narrower than the
OpenRefine review bridge:

```text
SensibLaw MigrationPack -> checked-safe CSV
```

Current contract:
- only rows already classified as:
  - `safe_equivalent`
  - `safe_with_reference_transfer`
- no drift/review rows
- no `split_required` rows
- no direct bot or QuickStatements emission

Current CSV fields:
- `candidate_id`
- `entity_qid`
- `slot_id`
- `statement_index`
- `classification`
- `action`
- `from_property`
- `to_property`
- `value`
- `rank`
- `qualifiers_json`
- `references_json`
- `target_claim_bundle_json`

Interpretation:
- this is a staging/export surface for already-safe rows only
- it is still not an edit command format
- downstream execution and post-edit verification remain separate gates

Immediate next policy goal:
- add a more precise action model for temporal/multi-value rows
- start by breaking some current `ambiguous_semantics` cases into
  `split_required` and related review actions
- keep execution/export claims gated until that action model exists
- if text-aware evidence is added later, route it through the bounded bridge
  contract in:
  `docs/planning/wikidata_phi_text_bridge_contract_20260328.md`
  rather than letting raw text interpretation bypass promotion or override the
  structured lane

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

## Live materializer helper
The bounded live helper now supports two QID population modes:

1. explicit inputs:
   - repeatable `--qid Q...`
   - or `--qid-file path/to/qids.txt`
2. bounded live discovery:
   - `--discover-qids`
   - `--candidate-limit N`
   - discovery is based on the source property and returns the exact QIDs used
     in the materialized manifest

Example with explicit QIDs:

```bash
.venv/bin/python SensibLaw/scripts/materialize_wikidata_migration_pack.py \
  --qid Q56404383 \
  --qid Q10651551 \
  --source-property P5991 \
  --target-property P14143 \
  --out-dir /tmp/p5991_p14143_pack
```

Example with bounded live discovery:

```bash
.venv/bin/python SensibLaw/scripts/materialize_wikidata_migration_pack.py \
  --discover-qids \
  --candidate-limit 10 \
  --source-property P5991 \
  --target-property P14143 \
  --out-dir /tmp/p5991_p14143_pack
```

One-step materialization plus OpenRefine CSV:

```bash
.venv/bin/python SensibLaw/scripts/materialize_wikidata_migration_pack.py \
  --discover-qids \
  --candidate-limit 10 \
  --source-property P5991 \
  --target-property P14143 \
  --out-dir /tmp/p5991_p14143_pack \
  --openrefine-csv /tmp/p5991_p14143_pack_openrefine.csv
```

Export a materialized migration pack to OpenRefine CSV:

```bash
sensiblaw wikidata export-migration-pack-openrefine \
  --input path/to/migration_pack.json \
  --output path/to/migration_pack_openrefine.csv
```

Export only the checked-safe subset:

```bash
sensiblaw wikidata export-migration-pack-checked-safe \
  --input path/to/migration_pack.json \
  --output path/to/migration_pack_checked_safe.csv
```

Verify the checked-safe subset against an after-state slice/export:

```bash
sensiblaw wikidata verify-migration-pack \
  --input path/to/migration_pack.json \
  --after path/to/after_state_slice.json \
  --output path/to/migration_verification.json
```

Current verification statuses:
- `verified`
- `duplicate_target`
- `target_present_but_drifted`
- `target_missing`

Current verification checks:
- only the checked-safe subset is examined
- does the exact target bundle exist in the after-state?
- if not exact, is there at least a same-value same-rank target row with drift?
- does the old source bundle still remain present?

## Split-plan followthrough
The next artifact after `split_required` detection is now a separate review-only
contract:
- note:
  `docs/planning/wikidata_split_plan_contract_20260328.md`
- schema:
  `schemas/sl.wikidata_split_plan.v0_1.schema.yaml`
- CLI:
  `sensiblaw wikidata build-split-plan`

Boundary:
- `MigrationPack` detects and explains split pressure
- `SplitPlan` proposes structurally decomposable `1 -> N` target bundles
- neither artifact is yet a direct split executor

## Non-goals
- no direct bot or QuickStatements emission
- no claim of semantic non-equivalence beyond the implemented buckets
- no automatic use of WikiProject consensus as promotion truth
- no direct edit execution in `v0.1`

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
4. DONE: add a checked-safe export surface after the pinned pack exists.
5. DONE: add bounded post-edit verification over the checked-safe subset.
6. Define the first bounded bridge between:
   - structured migration-pack rows
   - promoted text observations
   - pressure outputs such as `reinforce`, `split_pressure`,
     `contradiction`, and `abstain`
