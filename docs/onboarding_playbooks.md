# Ontology Onboarding Playbooks

This guide walks teams through onboarding new legal systems and value frames so
they land cleanly in the layered ontology and downstream applications.

## New legal system onboarding

1. **Model the jurisdiction**
   - Add a `LegalSystem` row with canonical name, ISO-style region codes, and
     primary `NormSourceCategory` mappings (constitution, legislation, case
     law, tikanga/indigenous sources).
   - Capture citation templates for common sources (constitution, general
     acts, delegated legislation) in source manifests.
2. **Seed authoritative sources**
   - Register `LegalSource` rows for foundational materials (constitution,
     enabling statutes, leading codes) and include `Provision` scaffolding when
     available.
   - Ensure citations are unique across the jurisdiction; run
     `python scripts/validate_integrity.py` after adding manifests to guard
     against duplicates.
3. **Bridge into ontology layers**
   - Link initial `WrongType` rows to their `LegalSource` anchors via
     `WrongTypeSourceLink` using relation types (`creates`, `defines`,
     `modifies`, `leading_case`).
   - Map core `ProtectedInterest` and `ValueFrame` context so inference and UI
     pathways have evaluative hooks.
4. **Quality gates and publication**
   - Add fixtures representing canonical provisions and sample cases into
     `tests/fixtures/` and extend ingestion smoke tests.
   - Submit a migration plan describing new tables or enums, and document
     rollout windows in `docs/ontology_versioning.md` for MAJOR impacts.

## New value frame onboarding

1. **Define the frame**
   - Document the evaluative axes, scoring rubric, and relationship to existing
     frames (complements vs supersedes) in `docs/ontology_versioning.md`.
   - Introduce aliases and localized labels so inference and UI components can
     resolve text mentions.
2. **Attach to wrong types and remedies**
   - Identify the `WrongType` cohorts that use the new frame and add
     `WrongTypeValueFrame` or equivalent bridge rows.
   - Update `Remedy` metadata where selection logic depends on the frame
     (weights, eligibility criteria, or outcome dimensions).
3. **Migrations and safeguards**
   - Ship migration scripts that backfill `ValueFrameEvaluation` rows for
     existing `WrongTypeInstance` records, preserving prior scores as
     historical entries.
   - For MAJOR frame changes, publish deprecation mappings and provide a
     backward-compatible interpretation layer (e.g., translating old scores to
     new axes) until consumers switch.
4. **Testing and CI**
   - Add fixtures for the new frame (example evaluations, scoring matrices) and
     extend ontology validation tests.
   - Ensure CI runs `python scripts/validate_integrity.py` to catch citation or
     cultural flag regressions introduced alongside value frame updates.
