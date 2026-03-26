# Wikidata Structural Review Summary

- Review items: 9
- Source review rows: 16
- Review-required items: 4
- Related review clusters: 4
- Candidate structural cues: 25
- Provisional review rows: 25
- Provisional review bundles: 9

## Workload Classes

- baseline_confirmation: 2
- cluster_promotion_gap: 8
- governance_gap: 3
- qualifier_drift_gap: 1
- structural_contradiction: 2

## Normalized Metrics

- Review-item statuses: accepted `5`, review_required `4`, held `0`
- Source statuses: accepted `10`, review_required `6`, held `0`
- Dominant primary workload: `structural_pressure`
- Primary workload counts:
  - `structural_pressure` `3`
  - `governance_pressure` `3`
  - `linkage_pressure` `0`
  - `event_or_time_pressure` `0`
  - `evidence_pressure` `0`
  - `normalization_pressure` `0`
  - `queue_pressure` `0`
- Workload presence counts:
  - `structural_pressure` `3`
  - `governance_pressure` `3`
  - `linkage_pressure` `0`
  - `event_or_time_pressure` `0`
  - `evidence_pressure` `0`
  - `normalization_pressure` `0`
  - `queue_pressure` `0`
- Review-required source ratio: `0.375000`
- Candidate signal count: `11`
- Candidate signal density: `1.833333`
- Provisional queue rows: `25`
- Provisional row density: `4.166667`
- Provisional bundles: `9`
- Provisional bundle density: `1.500000`

## Related Review Clusters

- Hotspot pack software_entity_kind_collapse_pack_v0: 3 review rows, governance_gap, cues=hold_reason (1), sample_question (2), source_artifact (1).
  recommended action: promote held hotspot pack through manifest governance
- Disjointness case fixed_construction_contradiction: 1 review rows, structural_contradiction, cues=pair_label (1), violation_counts (1).
  recommended action: review contradiction culprits and preserve disjointness evidence
- Disjointness case working_fluid_contradiction: 1 review rows, structural_contradiction, cues=pair_label (1), violation_counts (1).
  recommended action: review contradiction culprits and preserve disjointness evidence
- Qualifier drift case Q100104196|P166: 1 review rows, qualifier_drift_gap, cues=qualifier_property_set (1), qualifier_signature_delta (2).
  recommended action: inspect qualifier signature drift across revision windows

## Top Provisional Review Bundles

- #1 review:disjointness_case:fixed_construction_contradiction with 2 cues, top score 108.
- #2 review:disjointness_case:working_fluid_contradiction with 2 cues, top score 108.
- #3 review:hotspot_pack:software_entity_kind_collapse_pack_v0 with 4 cues, top score 91.
- #4 review:qualifier_drift:Q100104196|P166 with 3 cues, top score 84.
- #5 review:hotspot_pack:mixed_order_live_pack_v1 with 4 cues, top score 70.
