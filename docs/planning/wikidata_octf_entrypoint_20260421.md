# Wikidata OCTF Entrypoint

Date: 2026-04-21

## Purpose

Give the Wikidata Ontology Cleaning Task Force one practical entry point into
the current work.

This note is for reviewers who want to know:

- where to start
- what is runnable
- what can be checked
- what should not be inferred

## Short version

The repo is strongest at turning imperfect Wikidata signals into bounded review
artifacts.

Signals can come from:

- subclass or instance checks
- disjointness checks
- constraint checks
- LLM suggestions
- external scaffolds such as DBpedia or SUMO

The repo should not treat those signals as edit authority. The working pattern
is:

1. materialize a bounded slice
2. classify it into explicit buckets
3. expose a reviewer-facing report or pack
4. stage only the checked-safe subset
5. verify after any edit

That makes the current work a review/check layer, not an approval layer and not
a blind edit bot.

## Best first path

Start with the climate migration lane because it has the clearest end-to-end
artifact:

- source property: `P5991` (`carbon footprint`)
- target property: `P14143` (`annual greenhouse gas emissions`)
- pilot pack:
  `SensibLaw/data/ontology/wikidata_migration_packs/p5991_p14143_climate_pilot_20260328/`

Read these first:

1. `SensibLaw/docs/wikidata_working_group_status.md`
2. `SensibLaw/docs/planning/wikidata_migration_pack_contract_20260328.md`
3. `SensibLaw/docs/planning/wikidata_ontology_group_handoff_nat_lane_20260401.md`

If you want the simplest plain-language handoff, read:

- `SensibLaw/docs/planning/wikidata_shixiong_handoff_20260402.md`

That file is named for a specific collaborator, but it is currently the shortest
plain-language overview of the migration/review lane.

## Programmatic entry points

The main CLI entry points are under the Wikidata command group.

Local repo invocation used in the existing docs:

```bash
cd SensibLaw
../.venv/bin/pip install -e .[dev,test]
../.venv/bin/python -m cli.__main__ wikidata --help
```

Climate migration pack:

```bash
cd SensibLaw
../.venv/bin/python -m cli.__main__ wikidata build-migration-pack \
  --input data/ontology/wikidata_migration_packs/p5991_p14143_climate_pilot_20260328/slice.json \
  --source-property P5991 \
  --target-property P14143 \
  --output /tmp/p5991_p14143_migration_pack.json
```

OpenRefine review export:

```bash
cd SensibLaw
../.venv/bin/python -m cli.__main__ wikidata export-migration-pack-openrefine \
  --input data/ontology/wikidata_migration_packs/p5991_p14143_climate_pilot_20260328/migration_pack.json \
  --output /tmp/p5991_p14143_openrefine.csv
```

Checked-safe-only export:

```bash
cd SensibLaw
../.venv/bin/python -m cli.__main__ wikidata export-migration-pack-checked-safe \
  --input data/ontology/wikidata_migration_packs/p5991_p14143_climate_pilot_20260328/migration_pack.json \
  --output /tmp/p5991_p14143_checked_safe.csv
```

Post-edit verification:

```bash
cd SensibLaw
../.venv/bin/python -m cli.__main__ wikidata verify-migration-pack \
  --input data/ontology/wikidata_migration_packs/p5991_p14143_climate_pilot_20260328/migration_pack.json \
  --after path/to/after_state_slice.json \
  --output /tmp/p5991_p14143_verification.json
```

Split-plan review surface:

```bash
cd SensibLaw
../.venv/bin/python -m cli.__main__ wikidata build-split-plan \
  --input data/ontology/wikidata_migration_packs/p5991_p14143_climate_pilot_20260328/migration_pack.json \
  --output /tmp/p5991_p14143_split_plan.json
```

## Parallel review lanes

The same review-first pattern also exists in two structural ontology lanes.

Structural hotspot packs:

- docs:
  `docs/planning/wikidata_hotspot_pack_contract_20260325.md`
- manifest:
  `docs/planning/wikidata_hotspot_pilot_pack_v1.manifest.json`
- CLI:

```bash
cd SensibLaw
../.venv/bin/python -m cli.__main__ wikidata hotspot-generate-clusters \
  --manifest ../docs/planning/wikidata_hotspot_pilot_pack_v1.manifest.json \
  --output /tmp/wikidata_hotspot_clusters.json
```

Bounded disjointness diagnostics:

- docs:
  `docs/planning/wikidata_disjointness_report_contract_v1_20260325.md`
- case index:
  `docs/planning/wikidata_disjointness_case_index_v1.json`
- CLI:

```bash
cd SensibLaw
../.venv/bin/python -m cli.__main__ wikidata disjointness-report \
  --input path/to/bounded_disjointness_slice.json \
  --output /tmp/wikidata_disjointness_report.json
```

## Current review question

The useful question for OCTF is not whether every candidate signal should become
an edit.

The useful question is:

- does this bounded report or pack expose enough information for a reviewer to
  decide whether the case is safe, split-required, repair-needed, held, or
  reconstruct-only?

For the climate lane, the current routing boundary is:

- annual organization-level emissions can route toward `P14143`
- product or lifecycle carbon footprint stays on `P5991`
- emissions intensity, avoided emissions, offsets, and removals stay held until
  a specific target property is confirmed
- non-emissions metrics are blocked

## What not to infer

- This is not a claim that the repo solves Wikidata ontology correctness.
- This is not a claim that LLMs can decide edits.
- This is not a claim that DBpedia or SUMO can be imported as constraints.
- This is not a direct bot execution plan.
- This is not an approval workflow.

The claim is narrower:

- candidate signals should become bounded review artifacts first
- only locally complete, checked-safe rows should be staged
- uncertain rows should remain visibly uncertain
