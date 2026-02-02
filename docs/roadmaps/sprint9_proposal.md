# Sprint 9 Proposal — Operational Auditability at Scale (Non-Reasoning)

## Goal (restated)
Enable human review, comparison, and export of existing obligation artifacts **without** adding reasoning, inference, or semantic mutation.

## Scope (allowed)
- Consume existing payloads only: `obligation.v1`, `obligation.activation.v1`, `obligation.crossdoc.v1`, `review.bundle.v1`.
- Human metadata: `ReviewerNote`, `DisagreementMarker`, optional `ReviewStatus` (workflow-only).
- Collection handling: load multiple bundles, compare presence/absence, export manifests.
- UI: read-only Streamlit panels, filters, grouping, sorting, visual diffs of payload equality.
- Exports: deterministic JSON/PDF bundles with manifest + hashes.

## Non-goals / Do NOT touch
- ❌ No compliance, satisfaction, or correctness judgments.
- ❌ No precedence/priority logic or conflict resolution.
- ❌ No temporal inference (“still applies”, “ceased”).
- ❌ No ontology/synonym expansion.
- ❌ No changes to extraction, activation logic, cross-doc grammar, or identity hashing.
- ❌ No edits to any `*.v1` schema (new semantics → new version).
- ❌ No UI controls that mutate payloads (approve/resolve/fix).

## Deliverables
1) **review.collection.v1** schema: references to multiple review bundles with labels.
2) **Streamlit collection view**: bundle picker + side-by-side obligation/activation/topology diffs (structural only).
3) **Deterministic export pipeline**: `sensiblaw review export` → zip(JSON, PDF render, manifest with hashes).
4) **Workflow metadata (optional, side-band)**: `ReviewStatus` (stage, owner, timestamp) stored outside bundles; stripping it yields identical bundle hashes.

## Tests / Red-flag guards
- Red-flag: removing annotations/workflow metadata restores identical hashes.
- Red-flag: no forbidden terms (“compliance”, “breach”, “winner”, “prevails”) in UI or exports.
- Schema validation for `review.collection.v1` and exports.
- Snapshot diffs of collection view (structural equality only).

## Exit criteria
- All existing v1 schemas untouched; new schemas versioned if added.
- Red-flag suite green.
- Collection diff introduces **no new facts** beyond set membership/equality.
- Exports reproducible: same inputs → identical bytes + manifest hashes.

## Work plan (4 steps)
1) **Schema + fixtures**
   - Add `schemas/review.collection.v1.schema.yaml`.
   - Fixture: `examples/review_collection_minimal.json`.
   - Tests: schema validation; ordering changes must not affect hashes; reordering bundles should not change manifest.
2) **Collection diff logic**
   - Pure function to compare bundles (byte-level): added/removed/changed sections for obligations, activation, topology.
   - Tests: structural diff only; no semantic assertions.
3) **Streamlit integration**
   - New tab “Collections”: bundle picker + structural diff view.
   - Read-only; no mutation controls.
4) **Export pipeline**
   - CLI: `python -m sensiblaw.cli review export --collection examples/review_collection_minimal.json`.
   - Outputs: zip (bundles + manifest + optional PDF render).
   - Tests: manifest hashes deterministic across runs.

## Out of scope (defer to future sprint/repo)
- Any reasoning/interpretation module.
- Precedence or conflict resolution.
- Obligation satisfaction/compliance answers.
- Ontology/semantic normalization.
