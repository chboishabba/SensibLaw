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

## Why this is relevant to your work

Your recent paper is about three things that matter here:

- validating whether a Wikidata problem is real
- deciding whether it is actually worth correcting
- giving people a system they can inspect rather than a black-box claim

That is a good fit for this lane.

The overlap is not "classification hierarchy" itself.

The overlap is the method:

- bounded validation instead of broad hand-waving
- explicit criteria for when a change is justified
- reviewer-facing inspection surfaces
- conservative correction posture

There is also a second overlap around evidence quality.

This lane is strict about qualifier and reference preservation, and it does not
want weak provenance, path-only artifacts, or silent semantic jumps.

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

The strongest current lesson is simple:

- the hard part is not detecting candidate rows
- the hard part is deciding when a proposed correction is really warranted
- most pressure is in split/review, not bulk rewrite

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

If your paper's "inspect the relationships before deciding to correct them"
idea is the mental model, that is close to what these packets are trying to do
for migration rows.

## What is not done yet

These are the main missing pieces:

- broader packet coverage across held rows
- richer review buckets such as:
  - `needs_human_review`
  - `non_equivalent`
- clearer packet/workbench support for the hard split-heavy rows
- more real reviewed text-linked evidence for climate cases
- broader execution confidence beyond the checked-safe subset
- a sharper explicit criterion for when a held row should actually be corrected
  rather than just flagged

## Best files to read first

Read these in this order:

1. Current group status:
   - `SensibLaw/docs/wikidata_working_group_status.md`
2. Migration protocol:
   - `SensibLaw/docs/planning/wikidata_climate_change_property_migration_protocol_20260327.md`
3. Reviewer packet contract:
   - `SensibLaw/docs/planning/wikidata_review_packet_contract_20260401.md`
4. Migration pack contract:
   - `SensibLaw/docs/planning/wikidata_migration_pack_contract_20260328.md`
5. Nat end-product note:
   - `SensibLaw/docs/planning/wikidata_nat_end_product_and_tiered_automation_20260401.md`

If you only have time for two files, read:

- `SensibLaw/docs/wikidata_working_group_status.md`
- `SensibLaw/docs/planning/wikidata_review_packet_contract_20260401.md`

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
4. help define a correction-worthiness rule that is clear enough for reviewers
   to use without overstating certainty

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

- review the current packet and migration-pack contracts
- look at the pilot pack and the split-heavy rows
- pressure-test whether the current packet surface is good enough for a human
  reviewer to decide "correct", "split", or "hold"
- help us think clearly about when a row is:
  - safely transferable
  - split-required
  - not equivalent
  - still too uncertain
  - visible but not worth correcting yet

That is the current high-value discussion.
