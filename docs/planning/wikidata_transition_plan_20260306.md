# Wikidata Transition Plan (2026-03-06)

## Scope
Build a deterministic, reviewable Wikidata “control-plane” layer that projects
statement bundles into ternary epistemic states (v0.1 operator), measures
instability (EII), and ties diagnostics to class-order pathologies. This plan
bridges the existing external-ontology ingestion (curation-time) with the new
Wikidata diagnostics stack, without changing normative/authority boundaries.

## Inputs Reviewed
- `docs/wikidata_epistemic_projection_operator_spec_v0_1.md`
- `docs/wikidata_ontology_issue_review_20260306.md`
- `docs/external_ontologies.md`
- `docs/external_ingestion.md`
- `docs/ONTOLOGY_EXTERNAL_REFS.md`
- `docs/wikidata_queries.md`
- `docs/dbpedia_integration.md`

## Goals (v0.1)
- Deterministic projection of Wikidata statement bundles into ternary states.
- Minimal, auditable EII computation across time windows/dumps.
- Diagnostics mapped to observed issue clusters (class/instance confusion,
  subclass loops, qualifier drift, metaclass misuse, negative constraints).
- A reporting surface that complements class-order diagnostics (SCCs, loops),
  not a fix recommender.
- Alignment with tokenizer/lexeme contracts so canonical span and pre-semantic
  layers remain untouched by Wikidata semantics.

## Non-Goals (v0.1)
- No source reliability scoring or ML inference.
- No auto-fix proposals or ontology governance prescriptions.
- No changes to internal ontology authority rules.

## Constraints / Guardrails
- Deterministic, replayable outputs from the same input bundles.
- Paraconsistent aggregation (conflict becomes explicit, not collapsed).
- Wikidata integration remains advisory only (consistent with
  `docs/external_ontologies.md`).
- All outputs must be auditable and explainable via structured traces.
- Treat projection as a transformation of observations, aligned with
  `docs/planning/time_series_transformations.md` (Niklas model).
- Canonical text, token, and lexeme layers remain authoritative for source
  provenance; Wikidata diagnostics are downstream read-only overlays.
- No regex-first or generative disambiguation in authoritative mapping paths.

## Bounded first slice
Primary executable slice:
- `P31`
- `P279`

First review outputs:
- mixed-order (`P31` / `P279`) findings
- `P279` SCCs
- metaclass-heavy neighborhoods

Deferred from the first executable slice:
- qualifier entropy / qualifier drift
- negative constraints beyond review notes
- broader external-ref workflow automation

---

## Phase 1 — Spec Hardening + Diagnostic Taxonomy
**Goal:** Lock the formal spec + diagnostic taxonomy and ensure alignment with
existing ingestion and external-refs workflows.

Deliverables:
- `docs/ontology_diagnostic_taxonomy_wikidata_v0_1.md`
  - Deterministic checks mapped to issue clusters (from issue review).
  - Explicit non-goals and audit trace requirements.
- `docs/wikidata_epistemic_projection_operator_spec_v0_1.md` appendix:
  - Diagnostic lens rules (EII + SCCs + qualifier entropy).
- Alignment note in `docs/external_ontologies.md`:
  - Prevent metaclass escalation during external ID mapping.

Exit criteria:
- Taxonomy doc reviewed, minimal rule set agreed.
- Spec + taxonomy cross-referenced and self-consistent.
- Tokenizer/lexeme boundary note is explicit in `docs/external_ontologies.md`.

---

## Phase 2 — Data Slice + Operator Prototype
**Goal:** Implement a minimal projection pipeline on a bounded Wikidata slice.

Deliverables:
- `src/wikidata/` (or `src/ontology/wikidata/`) module with:
  - Statement bundle parser
  - Projection operator `Pi`
  - Aggregator `A`
  - EII calculator (two time windows)
  - Structured audit trace schema
- A small, reproducible slice input:
  - Two dumps or two edit windows
  - Focused on `P31`, `P279` and a curated property set
- CLI entrypoint (internal):
  - `python -m cli wikidata project --input ... --output ...`

Exit criteria:
- Deterministic output for the same input.
- Minimal EII report (top N unstable slots + trace summaries).

---

## Phase 3 — Diagnostics + Class-Order Coupling
**Goal:** Correlate EII volatility with class-order pathologies.

Deliverables:
- SCC detection over `P279` subgraph for the same slice.
- Diagnostic report:
  - Volatile SCC neighborhoods
  - Class/instance boundary confusion counts
  - Qualifier entropy hotspots
- Optional export into graph JSON for visualization.

Exit criteria:
- Report is consistent across runs and clearly tied to diagnostics taxonomy.

---

## Phase 4 — Integration + Reporting Surfaces
**Goal:** Provide a stable, non-prescriptive reporting surface for reviewers.

Deliverables:
- Report schema + JSON export (machine-readable, deterministic).
- Markdown summary generator (human-readable):
  - Top unstable properties/subgraphs
  - Traceable reasons (rank flips, ref changes, qualifier drift)
- Optional UI hook for Streamline/QA surfaces (read-only).

Exit criteria:
- Reports can be produced end-to-end without manual steps.
- Reviewers can trace any unstable slot to its audit trace.

---

## Risks / Open Questions
- **Dump access & size:** Do we have a reproducible, versioned slice to use?
- **Qualifier normalization:** What minimal canonicalization rules are safe?
- **Evidence gate:** What is the initial `e0` threshold for rank gating?
- **Conflict semantics:** Is the paraconsistent aggregate sufficient for v0.1,
  or do we need a conflict score decomposition in the report?

## Working-team handoff
Initial material for Niklas / Ege / Peter should include:
- `docs/wikidata_working_group_status.md`
- the diagnostic taxonomy
- the projection spec plus diagnostic appendix
- the bounded-slice definition (`P31` / `P279`)
- a reviewer-facing summary template listing SCCs, mixed-order nodes, and
  metaclass-heavy regions
- `docs/planning/wikidata_working_group_review_template_20260307.md`
- `docs/planning/wikidata_working_group_review_pass_20260307.md`
- `docs/wikidata_report_contract_v0_1.md`

## Immediate Next Actions
1. Import more real `P31` / `P279` neighborhoods via `wikidata build-slice` before expanding to qualifier drift.
2. Validate severity/ranking on a larger mixed-order sample.
3. Reconfirm whether a live SCC example should be added to the review pack.
4. Defer qualifier entropy until the `P31` / `P279` review pack is materially broader.
