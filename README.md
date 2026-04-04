# SensibLaw

SensibLaw is the suite's deterministic review and provenance layer.

In plain language, it takes difficult source material and turns it into
structured, inspectable outputs instead of opaque summaries. It is used for
legal/normative review, structured evidence handling, and bounded ontology
diagnostics such as the current Wikidata work.

## What SensibLaw Does

SensibLaw currently provides:

- ingestion of source material into structured, anchored artifacts
- deterministic review/report surfaces instead of free-form narrative output
- provenance-backed JSON artifacts and handoff bundles
- bounded Wikidata diagnostics over pinned slices
- export/handoff paths into downstream reasoning and review layers such as
  Zelph

The current architecture direction is no longer lane-by-lane growth. It is a
single normalized process that different source families and work lanes bind
onto over time.

The important design choice is that SensibLaw is not trying to be "the model
that knows the answer." It is trying to preserve source traceability while
making reviewable structure.

## What You Can Do With It Today

### 1. Build structured review artifacts from messy source material

SensibLaw can turn source material into:

- structured slices
- projections
- review queues
- handoff bundles
- provenance-aware JSON outputs

Why that matters:

- a later reviewer can inspect what was extracted
- uncertainty and disagreement can stay visible
- downstream systems do not need to depend on ad hoc notes

### 2. Run bounded Wikidata review/diagnostic workflows

This is one of the clearest current external examples of SensibLaw doing
something real.

Current repo-backed examples include:

- a clean baseline around `nucleon` / `proton` / `neutron`, where the
  disjointness relation is present but there are no violations
- a real contradiction around `working fluid`, where `working fluid` is typed
  as both `gas` and `liquid`
- a real contradiction in the `fixed construction` / `geographic entity` area,
  where the current pinned slice shows several subclass violations
- a synthetic transport example used to keep the reporting deterministic, with
  amphibious/land/water subclass and instance violations

What those examples imply:

- the lane can preserve a genuine zero-violation baseline
- it can catch direct instance-level contradictions
- it can also catch longer structural subclass problems
- it can present those findings in reviewer-facing summaries rather than only
  raw graph output

### 3. Produce checked handoff artifacts

SensibLaw already has bounded, checked handoff outputs for multiple lanes.

That matters because the outputs are:

- stable enough to discuss with collaborators
- backed by repo artifacts and tests
- explicit about what is demonstrated and what is not yet being claimed

## Proven Abilities

These are the strongest current categories to point at.

### Bounded Wikidata structural review

SensibLaw can already:

- turn live or imported Wikidata slices into deterministic reports
- preserve zero-violation baselines
- surface direct contradictions
- surface subclass contradiction chains
- package those outputs into checked summaries and fixture-backed artifacts

### Bounded Nat automation proof

SensibLaw now also has one bounded measured-automation success in the Nat
`P5991 -> P14143` lane:

- exact promoted subset:
  `Q1068745|P5991|1` and `Q1489170|P5991|1`
- scope:
  pilot-ready only for that exact family subset
- non-claim:
  this does not establish broader Cohort A or backlog-wide automation

The next Nat bottleneck is not more proof for those two rows. It is
independent evidence for a second structural family.

The Nat lane now also has the bounded evidence lifecycle around that blocker:

- `AWAITING_EVIDENCE` families emit machine-readable intake contracts
- intake contracts can be aggregated into an acquisition backlog
- routed acquisition tasks can accept supplied evidence bundles
- same-family acquisition can be built directly from a revision-locked entity
  export and must still survive the existing verification step
- successful acquisition can move a family to `READY_TO_RERUN`
- reruns still have to pass the same convergence and governance path before
  any promotion claim is allowed
- some held families also now need a migration-aware read:
  `MIGRATION_PENDING` explains that the upstream migration protocol is active
  but the required after-state is not yet observed; it is explanatory state,
  not a promotion shortcut

Current held second-family seeds are:

- `climate_family_safe_reference_transfer_subset`
- `parthood_family_safe_reference_transfer_subset`

`parthood_family_safe_reference_transfer_subset` is now the primary second-family
proving target. As of April 4, 2026 its bounded live candidate set is:
`Q16572|P361|1`, `Q3700011|P361|1`, and `Q980357|P361|1`.
Its current same-family live acquisition route is still blocked, because the
bounded family migrates toward synthetic `P99999` and current live exports only
carry `P361`.
A bounded manual/acquired artifact path is now proven for `Q16572|P361|1`,
which is enough to move the family to `READY_TO_RERUN` through the existing
state machine even though the live same-family route still fails.
With acquired artifacts for the remaining two rows, the full parthood family is
also now proven to reach `PROMOTED` through the same generic acquisition and
convergence loop.
The same acquisition plan can now also drive a bounded live revision sweep over
recent Wikidata revisions and mark the family `PROMOTED` with
`state_basis = live_same_family_acquisition` when a later revision-locked
entity export actually verifies. The currently pinned live exports are still
blocked, so that proves live-path capability rather than a current live-data
success for parthood.
The Nat state machine now records a separate `state_basis`, so this result is
explicitly queryable as `supplied_acquired_artifact` rather than being
conflated with baseline runtime promotion or live same-family acquisition.

`climate_family_safe_reference_transfer_subset` now has a different read. It is
not just a thin held family. It is also a controlled migration lane:

- before-state is known: `P5991`
- desired after-state is known: `P14143`
- but the verifier still only counts real observed after-states

That means climate can be truthfully described as `MIGRATION_PENDING` where the
upstream migration protocol is active but the required `P14143` state is not
yet present in live source reality. This does not count as a second witness
and does not relax promotion.

That migration-aware read is now reflected in the runtime too:

- the Nat state machine can emit `MIGRATION_PENDING`
- climate intake routes now include:
  - `same_family_after_state`
  - `cross_row_migrated_p14143`
  - `text_bridge_promoted_observation`
- the repo carries a bounded `climate_family_v2_live_p14143_subset` seed for
  migrated-row confirmation against live `P14143` enterprise statements

The current highest-yield next move is therefore not more pressure on the same
thin climate row. It is:

- use a higher-churn live-backed family for the first observed
  `live_same_family_acquisition` promotion
- keep climate on a migration-aware recovery path through:
  - already-migrated row discovery
  - bounded cross-source confirmation
  - or legitimate family expansion if new safe climate rows become real

The broader `P5991` population is also now treated as semantically
heterogeneous rather than implicitly uniform. Nat can triage rows into:

- `direct_migrate`
- `split_required`
- `migration_pending`
- `out_of_scope`
- `needs_review`

That means the next scale lever is tighter segmentation and stronger abstention,
not more aggressive blanket automation across the whole property.

Nat now also has a bounded execution-side overlay:

- batch finder:
  selects promoted, live-target-capable families for migration work
- execution payload:
  shapes review-first OpenRefine / QuickStatements-compatible rows from
  checked-safe promoted candidates
- pre-execution contract layer:
  the repo now also owns explicit candidate contracts, backend routing plans,
  receipt contracts, and post-write verification contracts for operator handoff
- lifecycle overlay:
  `NOT_STARTED -> READY -> EXECUTED -> VERIFIED`

Current read:

- `business_family_reconciled_low_qualifier_checked_safe_subset` is the first
  execution-ready batch
- climate is still held and migration-aware, not execution-ready
- parthood can be promoted for convergence purposes, but its current synthetic
  target keeps it out of live execution batches
- operator-facing export, receipt ingestion, post-write verification, and proof
  CLI surfaces are now real locally
- but genuine external operator receipts still require an actual external
  action:
  a real review/export handoff, a real execution against Wikidata or an
  equivalent tool, and a real returned record of what was applied
- the repo can generate receipt schema, receipt examples, derived receipts from
  pinned exports, and proof bundles that consume receipts
- the repo cannot honestly generate evidence that an external write happened
  when it did not
- so the remaining blocker for operator-real status is provenance, not format
- the closure paths are:
  a real Nat handoff that writes back a receipt file, a QS/OpenRefine wrapper
  that emits receipts, or a manual signed receipt surface with applied rows and
  timestamps

Start here:

- [docs/wikidata_working_group_status.md](docs/wikidata_working_group_status.md)
- [../docs/planning/wikidata_disjointness_report_contract_v1_20260325.md](../docs/planning/wikidata_disjointness_report_contract_v1_20260325.md)
- [../docs/planning/wikidata_disjointness_case_index_v1.json](../docs/planning/wikidata_disjointness_case_index_v1.json)
- [tests/fixtures/zelph/wikidata_structural_handoff_v1/wikidata_structural_handoff_v1.summary.md](tests/fixtures/zelph/wikidata_structural_handoff_v1/wikidata_structural_handoff_v1.summary.md)

### Checked Zelph handoff paths

SensibLaw can already export small checked bundles for downstream reasoning
without pretending the entire corpus is complete.

Start here:

- [../docs/planning/gwb_zelph_handoff_v1_20260324.md](../docs/planning/gwb_zelph_handoff_v1_20260324.md)
- [../docs/planning/au_zelph_handoff_v1_20260324.md](../docs/planning/au_zelph_handoff_v1_20260324.md)
- [../docs/planning/zelph_real_world_pack_v1_6_20260325.md](../docs/planning/zelph_real_world_pack_v1_6_20260325.md)

### Deterministic review over provenance-backed artifacts

The broader point of SensibLaw is not just that it stores data. It provides a
bounded route from messy input to reviewed structure while keeping the source
trail visible.

## Quick Start

SensibLaw is usually worked on inside the top-level `ITIR-suite` workspace.

From the repo root:

```bash
./env_init.sh
cd SensibLaw
../.venv/bin/pip install -e .[dev,test]
```

Useful first commands:

```bash
../.venv/bin/python -m sensiblaw.cli --help
../.venv/bin/python -m pytest -q tests/test_wikidata_disjointness.py
../.venv/bin/python -m pytest -q tests/test_wikidata_structural_handoff.py
```

If you want the Streamlit surface:

```bash
../.venv/bin/streamlit run streamlit_app.py
```

Note:

- the test suite expects the superproject venv (`../.venv`)
- many docs and fixtures assume the full `ITIR-suite` workspace is present

## Common Workflows

### Wikidata diagnostics

Current operational entry points include:

```bash
../.venv/bin/python -m cli.__main__ wikidata build-slice
../.venv/bin/python -m cli.__main__ wikidata project
../.venv/bin/python -m cli.__main__ wikidata find-qualifier-drift
../.venv/bin/python scripts/run_wikidata_qualifier_drift_scan.py
```

Use this lane when you want bounded, pinned review artifacts rather than
generic ontology cleanup claims.

### CLI-first exploration

If you want to see what the current CLI exposes:

```bash
../.venv/bin/python -m sensiblaw.cli --help
../.venv/bin/python -m cli.__main__ --help
```

### Checked artifact review

If you want the fastest route to current examples, read the checked summaries
and fixture artifacts first, then drill down into the raw JSON/tests only if
needed.

## Where To Find Things

### Start here

- system/role overview:
  [docs/ITIR.md](docs/ITIR.md)
- architecture layers:
  [docs/ARCHITECTURE_LAYERS.md](docs/ARCHITECTURE_LAYERS.md)
- whole-system world-model view:
  [docs/roadmaps/world_model_metasystem_20260404.puml](docs/roadmaps/world_model_metasystem_20260404.puml)
- interfaces:
  [docs/interfaces.md](docs/interfaces.md)
- CLI examples:
  [docs/cli_examples.md](docs/cli_examples.md)

## Shared World-Model Process

SensibLaw is now converging toward one normalized process for all source
families rather than separate local truth models for Wikidata, AU, GWB,
Brexit, and future lanes.

That shared substrate currently exists in code as five ordered primitives:

1. cross-domain claim model
2. multi-source convergence
3. temporal update discipline
4. contradiction management
5. unified action policy

What this means in practice:

- source families should normalize into the same claim unit
- evidence should converge through the same governed merge surface
- later observations should relate to earlier ones through explicit temporal
  fields instead of silent overwrite
- contradictions should be represented explicitly rather than hidden in
  rejection
- action permissions should be downstream of evidence, convergence, temporal,
  and conflict state

Current status:

- the shared substrate exists in code
- Nat already emits the shared primitives additively in its convergence
  reports
- broader lane rebinding is still the next phase

This is the important distinction:

- `Nat` proves one source-adapter path into the substrate
- the world-model moonshot is the broader goal of rebinding all major lanes
  onto that same substrate

### Wikidata lane

- current status:
  [docs/wikidata_working_group_status.md](docs/wikidata_working_group_status.md)
- current review pass:
  [docs/planning/wikidata_working_group_review_pass_20260307.md](docs/planning/wikidata_working_group_review_pass_20260307.md)
- current report contract:
  [docs/wikidata_report_contract_v0_1.md](docs/wikidata_report_contract_v0_1.md)
- external-facing bounded handoff:
  [../docs/planning/wikidata_zelph_single_handoff_20260325.md](../docs/planning/wikidata_zelph_single_handoff_20260325.md)

### Ingestion and review docs

- ingestion:
  [docs/ingestion.md](docs/ingestion.md)
- end-to-end view:
  [docs/end_to_end.md](docs/end_to_end.md)
- how to review:
  [docs/how_to_review.md](docs/how_to_review.md)
- provenance:
  [docs/PROVENANCE.md](docs/PROVENANCE.md)

### Onboarding and ontology docs

- onboarding playbooks:
  [docs/onboarding_playbooks.md](docs/onboarding_playbooks.md)
- ontology overview:
  [docs/ontology.md](docs/ontology.md)
- ontology ER:
  [docs/ontology_er.md](docs/ontology_er.md)
- ontology/versioning:
  [docs/ontology_versioning.md](docs/ontology_versioning.md)

## What SensibLaw Is Not

SensibLaw is not:

- a generic chatbot
- a free-form legal-answer engine
- a silent auto-correction bot for Wikidata
- a substitute for human review

Its job is to make bounded structure and provenance easier to inspect, test,
and hand off.
