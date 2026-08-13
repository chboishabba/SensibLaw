# Demand occurrence support

`semantic_pnf_demand.source_object_id` is an optional one-object fast path, not the canonical provenance relation for a demand.

Migration 122 adds `semantic_pnf_demand_occurrence_support`, a many-valued carrier from a demand to structural occurrences already represented by the numeric PNF.

Strong support kinds are:

- `1`: exact object export on the same interface with the same lexical key and grammatical role;
- `2`: exact typed factor slot on the same interface with matching factor type and role.

Support kind `9` records the historical 090a `source_object_id` projection for audit only. H9 entity admission does not consume it.

Migration 125 redefines `source_object_id` as the unique projection of strong occurrence support. If no strong object exists, or if several exact objects remain possible, the column is `NULL`; the many-valued support carrier remains authoritative.

H9 entity-bearing and label-anchor views begin from `semantic_pnf_demand_strong_occurrence_support_v1`. Missing support is an unresolved provenance state, not negative semantic evidence.

The intended funnel is:

```text
H9 contract match
  -> strong demand occurrence support
  -> entity-bearing supported occurrence
  -> exact provider label anchor
  -> external need
```

Use `scripts/report_demand_occurrence_support.py` before any new Zelph/Wikidata run to measure exact support yield, parser-entity reachability, unique versus ambiguous source projections, legacy-only support, and a bounded sample of admitted labels.
