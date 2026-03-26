# Wikidata Structural Handoff Narrative Summary

This checked handoff artifact is a bounded wiki/Wikidata structural
review slice. It is meant to show, in plain language, what the repo can
already preserve and hand off from pinned structural diagnostics.

## Qualifier core

- The importer-backed baseline preserves 8 qualifier-bearing statements across 2 windows for P166 without surfacing drift.
- The pinned real drift case Q100104196|P166 remains checked at severity=medium from t1 to t2.

## Structural exemplars already ready for handoff

- mixed_order_live_pack_v1 (mixed_order) is already promoted with 6 generated clusters.
- p279_scc_live_pack_v1 (p279_scc) is already promoted with 4 generated clusters.
- qualifier_drift_p166_live_pack_v1 (qualifier_drift) is already promoted with 1 generated clusters.

## Structural review pressure kept explicit

- software_entity_kind_collapse_pack_v0 remains held/promotable: awaiting_manifest_promotion.
- GNU and GNU Project remain visible as review pressure rather than being over-promoted.
- nucleon_baseline is a zero-violation baseline for proton vs neutron.
- fixed_construction_contradiction is a real contradiction case for immaterial entity vs material entity: subclass_violations=4, instance_violations=0.
- working_fluid_contradiction is a real contradiction case for gas vs liquid: subclass_violations=0, instance_violations=1.

## Why this matters

- The handoff now has one human-readable checked slice instead of only scattered status notes.
- It shows both checked structural exemplars and explicit review pressure.
- It keeps the boundary clear: SensibLaw/ITIR diagnoses and preserves, while downstream reasoning stays bounded.

