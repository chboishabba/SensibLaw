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
- interfaces:
  [docs/interfaces.md](docs/interfaces.md)
- CLI examples:
  [docs/cli_examples.md](docs/cli_examples.md)

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
