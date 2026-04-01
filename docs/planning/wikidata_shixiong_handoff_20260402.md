# Wikidata Handoff For Shixiong Zhao

Date: 2026-04-02

## Purpose

Give Shixiong one short, practical entry point into the current Wikidata work.

This note is intentionally simple:

- what the project is doing
- what is already real
- what is not done
- which files matter
- where help is most useful

## One-minute summary

We are not trying to run a blind property migration bot.

We are building a review-first pipeline for one real migration problem:

- source property: `P5991` (`carbon footprint`)
- target property: `P14143` (`annual greenhouse gas emissions`)

The main idea is:

- easy rows should be separated from hard rows
- hard rows should become compact review packets
- nothing should be silently rewritten

So the product goal is:

- safe checked rows where they really exist
- split/review packets for the harder majority
- verification after edits

## What is already done

These pieces are real now:

- a concrete migration artifact:
  `MigrationPack v0.1`
- a schema-backed contract:
  `SensibLaw/schemas/sl.wikidata_migration_pack.v1.schema.yaml`
- a CLI builder:
  `sensiblaw wikidata build-migration-pack`
- first runtime buckets:
  - `safe_equivalent`
  - `safe_with_reference_transfer`
  - `qualifier_drift`
  - `reference_drift`
  - `split_required`
  - `abstain`
- checked-safe export:
  `sensiblaw wikidata export-migration-pack-checked-safe`
- OpenRefine CSV export:
  `sensiblaw wikidata export-migration-pack-openrefine`
- post-edit verification:
  `sensiblaw wikidata verify-migration-pack`
- split-plan support for hard rows:
  `sensiblaw wikidata build-split-plan`

## What the first real pilot shows

The first pinned live pilot pack is:

- `SensibLaw/data/ontology/wikidata_migration_packs/p5991_p14143_climate_pilot_20260328/`

That pilot proved something important:

- a very small subset may be safely migratable
- the larger real pressure is not “rename the property”
- the larger real pressure is split/review work

Later runtime changes made this even clearer:

- many rows that first looked generally ambiguous now classify as
  `split_required`

So the honest current position is:

- architecture: done enough
- protocol: done enough
- first executable artifact: done
- pilot migration review: possible
- full production migration execution: not done

## Nat lane in plain language

Nat is now best understood as a review-and-split workbench.

It is useful for:

- capturing bounded wiki proposal/review surfaces
- building migration packs and split plans
- attaching reviewer packets to hard rows
- reducing reviewer re-research

It is not yet a broad auto-execution lane.

## Reviewer packets in plain language

Reviewer packets are there to help with the hard rows.

A packet should show:

- the exact wiki source surface
- the split context
- the current qualifier/reference shape
- followed-source receipts where available
- what still seems unresolved
- the recommended next review step

Important boundary:

- the current parser is still shallow and bounded
- it is a review aid
- it is not a hidden semantic authority layer

## What is not done yet

These are the main missing pieces:

- broader packet coverage across held rows
- richer review buckets such as:
  - `needs_human_review`
  - `non_equivalent`
- clearer packet/workbench support for the hard split-heavy rows
- more real reviewed text-linked evidence for climate cases
- broader execution confidence beyond the checked-safe subset

## Best files to read first

Read these in this order:

1. Current group status:
   - `SensibLaw/docs/wikidata_working_group_status.md`
2. Migration protocol:
   - `SensibLaw/docs/planning/wikidata_climate_change_property_migration_protocol_20260327.md`
3. Migration pack contract:
   - `SensibLaw/docs/planning/wikidata_migration_pack_contract_20260328.md`
4. Nat end-product note:
   - `SensibLaw/docs/planning/wikidata_nat_end_product_and_tiered_automation_20260401.md`
5. Reviewer packet contract:
   - `SensibLaw/docs/planning/wikidata_review_packet_contract_20260401.md`

If you only have time for two files, read:

- `SensibLaw/docs/wikidata_working_group_status.md`
- `SensibLaw/docs/planning/wikidata_migration_pack_contract_20260328.md`

## Best places to look in the repo

- runtime:
  - `SensibLaw/src/ontology/wikidata.py`
- builder script:
  - `SensibLaw/scripts/materialize_wikidata_migration_pack.py`
- migration pack schema:
  - `SensibLaw/schemas/sl.wikidata_migration_pack.v1.schema.yaml`
- pinned pilot pack:
  - `SensibLaw/data/ontology/wikidata_migration_packs/p5991_p14143_climate_pilot_20260328/`
- packet fixture:
  - `SensibLaw/tests/fixtures/wikidata/wikidata_nat_review_packet_20260401.json`

## Where help is most useful now

The most useful help is not “how do we migrate all 50k rows?”

The most useful help is:

1. sharpen the meaning of the hard cases
2. help distinguish:
   - real split cases
   - real non-equivalent cases
   - cases that only need bounded human review
3. help decide what evidence is enough before a row leaves review-only status

In short:

- safe rows should stay genuinely safe
- hard rows should become easier to review
- uncertain rows should stay visibly uncertain

## What not to spend time on

- do not assume this is a simple property rename
- do not assume every `P5991` statement should become `P14143`
- do not assume the current reviewer packet parser is doing deep semantics
- do not spend time optimizing blind bulk execution

## Current honest ask

If Shixiong wants to engage quickly, the best immediate contribution is:

- review the current migration-pack and packet contracts
- look at the pilot pack and the split-heavy rows
- help us think clearly about when a row is:
  - safely transferable
  - split-required
  - not equivalent
  - still too uncertain

That is the current high-value discussion.
