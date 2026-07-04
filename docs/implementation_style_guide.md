# Implementation Style Guide

This guide is mandatory for new runtime code.

## Read Order

Before writing code, read:

1. `README.md`
2. `docs/itir_vs_sl.md`
3. this file

Agents and contributors should not start coding from local habit alone.

## Naming Rule

Lane identity belongs in:

- the module name
- the registry key
- the fixture/demo selector

Lane identity does **not** belong in public callable names.

Prefer:

- `build_report`
- `build_case`
- `build_contract`
- `build_receipt`
- `attach_receipt`
- `load_fixture`
- `build_manifest`
- `load_records`

Avoid:

- `build_lane_world_model_report_with_linkage_receipt`
- `attach_lane_pressure_linkage_receipt`
- `build_lane_review_bundle_linkage_case`

If the module is already `brexit.py`, `nat.py`, `au.py`, or `gwb.py`, the
callable must stay generic.

## Composition Rule

The public lane module may prefill a working demonstration, but it must do so
by composing lane-agnostic generic helpers.

Current generic linkage stack:

- `src/policy/linkage_adapters.py`
- `src/policy/linkage_depth.py`
- `src/policy/linkage_workflows.py`

Rule:

- the core audits
- the adapters emit
- the workflow helper attaches
- the lane module prefills

Do not put lane-specific control-plane logic into the shared helpers unless the
same audit concept is genuinely needed by multiple lanes.

## User-Surface Rule

Users should not be required to write lane glue code for common demonstrations.
Provide a lane module with generic verbs and prefilled selectors instead.

Examples:

- `src/ontology/nat.py` with `load_fixture(profile="climate_review_demonstrator")`
- `src/policy/brexit.py`
- `src/policy/au.py`
- `src/policy/gwb.py`

## Refactor Rule

When you notice a public callable whose name encodes both:

- the lane
- and the operation

pull the operation into a generic helper and leave the lane label at the module
or selector layer.
