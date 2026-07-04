# World Model Control-Plane

Date: 2026-07-04

## Rule

In SensibLaw/ITIR, a world model is a typed, versioned, source-bound candidate
carrier of possible world state. It is not a truth oracle and it does not
promote itself.

The required split is:

- `build_world_model(...)`
- `project_report(world_model)`
- `project_claim_table(world_model)`
- `project_timeline(world_model)`
- `project_review_surface(world_model)`
- `project_linkage_case(...)`
- `attach_receipt(...)`

## Ownership

- `src/policy/world_model.py`
  generic candidate world-model builders and normalizers
- `src/policy/world_model_projections.py`
  generic report/projection helpers
- `src/policy/world_model_profiles.py`
  generic lane/profile configuration helper
- lane modules
  compose candidate state and prefill demo surfaces
- linkage modules
  audit inspectable paths through projections

## Invariant

The world model may coalesce entities, claims, relations, events, timelines,
authority surfaces, provenance, conflicts, and residuals, but promotion still
requires an external authority/review surface plus an inspectable receipt.

## First Proof

The first proof modules in this tranche are:

- `src/policy/gwb_broader_review_world_model.py`
- `src/sources/national_archives/brexit_world_model_adapter.py`
- `src/sources/national_archives/brexit_national_archives_lane.py`
- `src/policy/au_world_model.py`

These now follow:

- build world model
- project report
- attach linkage receipt only at the lane boundary
