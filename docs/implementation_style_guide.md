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
- the lane-family wrapper such as `nat`

Lane identity does **not** belong in public callable names.

Profile identity belongs in selectors such as:

- `climate_review_demonstrator`
- `disjointness_report`
- `q43229_superclass_pressure`
- `broader_review`
- `narrative_timeline`

Prefer:

- `build_world_model`
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
- `src/policy/world_model.py`
- `src/policy/world_model_adapters.py`
- `src/policy/world_model_projections.py`
- `src/policy/world_model_profiles.py`

Rule:

- the world model carries candidate latent state
- projections expose reports, timelines, or claim tables
- the core audits
- the adapters emit
- the workflow helper attaches
- the lane module prefills

World-model rule:

- `world_model.py` owns carrier types only
- `world_model_adapters.py` owns artifact-to-carrier transformation
- `world_model_projections.py` owns inspectable views
- lane-local `*_world_model.py` files are transitional wrappers and should
  collapse toward profile config plus field mapping
- `build_world_model(...)` stays receipt-free
- `project_report(world_model)` stays receipt-free
- `project_claim_table(world_model)` stays receipt-free
- `project_timeline(world_model)` stays receipt-free
- `project_review_surface(world_model)` stays receipt-free
- `project_linkage_case(world_model)` stays receipt-free
- `attach_receipt(...)` happens only at the lane boundary

The generic `attach_receipt(...)` boundary accepts a linkage-case projection
or report that contains one; it does not accept a raw legacy artifact. A thin
lane compatibility wrapper may still accept its historical raw artifact, but
must first run the shared `build_world_model(...) -> project_report(...)` path
and only then call the generic receipt helper. This preserves one receipt
contract without making lane-local bundles a second shared input shape.

Do not put lane-specific control-plane logic into the shared helpers unless the
same audit concept is genuinely needed by multiple lanes.

## Entity Resolution and PNF Rule

Entity resolution is a shared compiler capability, not a GWB, AU, Nat, or
Wikidata method. New runtime work must follow the contract in
`docs/planning/pnf_driven_entity_resolution_spine_20260717.md`.

Required shape:

```text
canonical spans -> shared annotations -> locally typed candidate world fragment
-> partial PNF -> coverage/closure demands -> registry-neutral broker
-> bounded candidate evidence -> typed reconciliation -> PNF refinement
```

Implementation rules:

- preserve every token and make every logically meaningful span recoverable;
- instantiate the span/candidate lattice lazily rather than eagerly allocating
  every contiguous span;
- keep `candidate identity`, `resolved identity`, and `promoted fact` as
  separate authority states;
- keep ambiguity, rejected candidates, evaluation-budget exhaustion, and
  residuals explicit;
- share external entity snapshots and document-local coreference evidence by
  reference rather than copying them onto every mention;
- factorize PNF alternatives over one local skeleton until materialization is
  required for review or interacting constraints;
- treat external registries, including Wikidata, as optional revisioned
  evidence backends;
- type all meaningful entities and eventualities locally where supported;
  residual pressure controls evaluation depth, not candidate-world admission;
- keep parsers backend-blind and route external evidence through a generic
  cache-aware scheduler whose adapters may rate-limit and microbatch calls;
- distinguish event class, event occurrence, observation, cluster, forecast,
  report, alert, and rolling state, connecting them with explicit relations;
- define typed resolution subjects and formal event roles before scheduler or
  cache-key design; observations/clusters/forecasts/reports/alerts/states may
  not be coerced into event occurrences;
- deduplicate demands only by semantic equality over subject/role, local type
  alternatives, PNF slot role, typed constraints, requested facets, and
  document scope; surface equality is never sufficient;
- reconcile events through typed temporal, spatial, participant, type,
  lineage, and observation/occurrence obligations rather than a scalar score;
- treat WorldMonitor as an optional resolvable snapshot backend, not an event
  ontology or authority;
- prohibit silent/default cross-context identity merging;
- use `sensiblaw.interfaces` parser/reducer surfaces rather than raw regex,
  direct spaCy parsing, or lane-local tokenization.

The existing `GWBTargetingCandidate` and `GWBTargetingResult` classes are a
transitional lane-named surface. Do not deepen them. Extract reusable candidate
and targeting semantics into generic carriers, leaving the GWB module/profile
as fixture mapping and compatibility labeling only.

## User-Surface Rule

Users should not be required to know lane names or write lane glue code.
The primary product boundary is generic:

- `build_world_model(data)`
- `project_report(world_model)`
- `project_claim_table(world_model)`
- `project_timeline(world_model)`
- `project_review_surface(world_model)`
- `project_linkage_case(world_model)`
- `attach_receipt(...)`

Do not widen this boundary with lane/scenario selectors or adapter overrides
such as `profile=...`, `kind=...`, or `adapter_hint=...`. Demo and
compatibility wrappers may still carry internal routing metadata, but the
exported product API should remain data-in/world-model-out.

Lane modules may remain for demonstrations or compatibility only.

Examples of demo/compat layers:

- `src/ontology/nat.py` with `load_fixture(profile="climate_review_demonstrator")`
- `src/policy/brexit.py`
- `src/policy/au.py`
- `src/policy/gwb.py`

These are not the preferred product entry points.

## Refactor Rule

When you notice a public callable whose name encodes both:

- the lane
- and the operation

pull the operation into a generic helper and leave the lane label at the module
or selector layer.
