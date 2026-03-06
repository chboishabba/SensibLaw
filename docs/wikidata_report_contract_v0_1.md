# Wikidata Report Contract v0.1

## Purpose
Define the first reviewer-facing JSON contract for the bounded `P31` / `P279`
Wikidata control-plane report.

This contract is intentionally small and deterministic. It is for review and
working-group triage, not remediation.

## Top-level fields
- `schema_version`
- `bounded_slice`
- `assumptions`
- `windows[]`
- `unstable_slots[]`
- `qualifier_drift[]`
- `review_summary`

## `unstable_slots[]`
Required fields:
- `slot_id`
- `subject_qid`
- `property_pid`
- `from_window`
- `to_window`
- `tau_t1`
- `tau_t2`
- `delta_e`
- `delta_c`
- `eii`
- `present_in_both`
- `severity`

## Severity rules
- `high`
  - epistemic state changes between non-zero states (`+1 <-> -1`)
- `medium`
  - epistemic state changes with one side unresolved (`0 -> +1`, `0 -> -1`,
    `+1 -> 0`, `-1 -> 0`)
- `low`
  - no state change, but evidence/conflict deltas exist

## Sorting rules
`unstable_slots[]` are sorted by:
1. severity (`high`, `medium`, `low`)
2. `eii` descending
3. `present_in_both` true before false
4. `slot_id` ascending

This keeps reviewer attention on structurally comparable windows before
appearance/disappearance noise.

## `review_summary`
Required fields:
- `next_bounded_slice_recommendation`
- `unstable_slot_counts`
- `top_unstable_slot_ids`
- `structural_focus`
- `qualifier_drift_counts`
- `top_qualifier_drift_slot_ids`

Current default recommendation:
- qualifier drift is now active; expand qualifier-bearing slices and review
  property-set instability before wider ontology phases

## `qualifier_drift[]`
Required fields:
- `slot_id`
- `subject_qid`
- `property_pid`
- `from_window`
- `to_window`
- `qualifier_signatures_t1`
- `qualifier_signatures_t2`
- `qualifier_property_set_t1`
- `qualifier_property_set_t2`
- `qualifier_entropy_t1`
- `qualifier_entropy_t2`
- `qualifier_entropy_delta`
- `severity`

Severity rules:
- `high`
  - qualifier property set changes across windows
- `medium`
  - qualifier signatures change while the property set stays the same
- `low`
  - entropy changes without a property-set or signature-set change

## Window diagnostics
Each window report currently includes:
- `p279_sccs`
- `mixed_order_nodes`
- `metaclass_candidates`

Current reviewer priority:
1. mixed-order nodes
2. SCC neighborhoods
3. metaclass-heavy regions

Qualifier entropy / qualifier drift is phase 2 and now active in the report.

Current working-group entry point:
- `docs/wikidata_working_group_status.md`
