# Mabo Proof Explanation Profile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one canonical Mabo proof specimen that can drive the existing SLR research recurrence and project into a progressive Explain/Inspect/source/proof UI without duplicating legal semantics.

**Architecture:** SensibLaw remains the owner of legal propositions, authority/application, support/defeater/comparator roles, review/payment, and explanation. SLR receives a thin typed consumer profile and returns evidence/provenance/residual deltas through the already-validated binary recurrence. ITIR/Svelte renders query-indexed projections over the same canonical specimen; Wiki/Wikidata remains discovery/context, not legal authority.

**Tech Stack:** Python reference fixtures in SensibLaw only where already established; Rust/SLR binary recurrence; Agda parity in `dashi_agda`; SvelteKit + Tailwind in `ITIR-suite/itir-svelte`; PostgreSQL/world-store receipts as already implemented.

**Spec:** `docs/planning/mabo_proof_explanation_ui_roadmap_20260915.md`

## Global Constraints

- Production legal semantics stay in SensibLaw, not SLR.
- Python remains a reference/golden fixture for Mabo legal semantics, not the production SLR legal-semantic runtime.
- No JSON/NDJSON/JSONL/JSONB or regex semantic parser in the production SLR world path.
- Search snippets, Wiki/Wikidata, headnotes, and ontology candidates cannot pay strict primary-authority obligations.
- Exact primary-authority payment requires verified full source + exact span + admitted source role + review/payment.
- Progressive disclosure changes visibility only; every explanation-bearing claim remains reopenable to proof/source coordinates.
- Support, defeater, and comparator roles remain distinct.
- Literal user formulation and inferred intended issue remain distinct.

---

### Task 1: Canonical Mabo proof specimen contract

**Files:**
- Create: `src/pnf/mabo_proof_specimen.py`
- Create: `tests/pnf/test_mabo_proof_specimen.py`
- Reference: existing Mabo PNF/proof-search modules under `src/pnf/`

**Interfaces:**
- Consumes: existing Mabo proposition/issue/source-role objects.
- Produces: `MaboProofSpecimen`, `MaboExplanationClaim`, `MaboProofLink`, and projection-safe source/proof references.

- [ ] **Step 1: Write the failing tests** for one specimen containing literal formulation, inferred issue, authority candidate, applicability predicates, support, optional defeater/comparator, residual state, and exact source refs.
- [ ] **Step 2: Run the focused tests** and verify failure because the canonical specimen contract does not yet exist.
- [ ] **Step 3: Implement the minimal immutable specimen types** without generating prose or changing legal semantics.
- [ ] **Step 4: Re-run the focused tests** and confirm the specimen preserves role/source distinctions.
- [ ] **Step 5: Commit** with `feat(mabo): add canonical proof specimen contract`.

### Task 2: Thin SensibLaw -> SLR consumer-profile adapter

**Files:**
- Create: `src/pnf/mabo_slr_profile.py`
- Create: `tests/pnf/test_mabo_slr_profile.py`
- Create in SLR: `tools/slr-discourse-reconstruct/run_slr_mabo_proof_graph.sh`
- Create in SLR: `tools/slr-discourse-reconstruct/tests/test_slr_mabo_proof_graph_runner.py`

**Interfaces:**
- Consumes: `MaboProofSpecimen` residual/source-role requirements.
- Produces: existing SLRC-v2/SLRE-compatible requirements and typed SLR evidence/provenance deltas.

- [ ] **Step 1: Write tests** proving exact common ground emits zero new acquisition work and live contradiction/absence emits candidate-only authority/source requirements.
- [ ] **Step 2: Write SLR runner regression** requiring the existing binary recurrence and forbidding a Python Mabo semantic executor.
- [ ] **Step 3: Implement the adapter** as a translation of admitted SensibLaw obligations into existing SLR consumer/source-role coordinates.
- [ ] **Step 4: Implement the thin runner** over the existing bounded iteration runner; do not duplicate legal logic.
- [ ] **Step 5: Re-run focused SensibLaw/SLR tests** and commit.

### Task 3: Exact-source inspector projection

**Files:**
- Create: `src/pnf/mabo_source_projection.py`
- Create: `tests/pnf/test_mabo_source_projection.py`
- Create in ITIR-suite: `itir-svelte/src/lib/proof/sourceInspector.ts`
- Create in ITIR-suite: `itir-svelte/src/lib/proof/sourceInspector.test.ts`

**Interfaces:**
- Consumes: exact source/proof refs from `MaboProofSpecimen`.
- Produces: source identity, role, paragraph/section/span, version/revision, surrounding-context locator, and full-source action.

- [ ] **Step 1: Write tests** proving snippets/Wiki/headnotes are not primary-authority payment surfaces.
- [ ] **Step 2: Implement source projection** with explicit full-source/span requirements.
- [ ] **Step 3: Implement the Svelte read model** without duplicating proof state into DOM-local semantic state.
- [ ] **Step 4: Verify reopen from explanation -> exact source -> explanation** preserves specimen identity.
- [ ] **Step 5: Commit**.

### Task 4: Progressive Explain / Inspect projections

**Files:**
- Create in ITIR-suite: `itir-svelte/src/lib/proof/maboProjection.ts`
- Create in ITIR-suite: `itir-svelte/src/lib/proof/maboProjection.test.ts`
- Create in ITIR-suite: `itir-svelte/src/routes/graphs/mabo/+page.svelte`

**Interfaces:**
- Consumes: one canonical `MaboProofSpecimen` read model.
- Produces: `Explain`, `Why`, `Source`, `Context`, and `Graph` projections only.

- [ ] **Step 1: Write tests** that default Explain hides internal IDs while retaining proof/source reopen refs.
- [ ] **Step 2: Implement Explain** with bounded chain and `What still needs checking` / `What this does not establish`.
- [ ] **Step 3: Implement Why/contingent-arguments expansion** for the selected proposition only.
- [ ] **Step 4: Implement Inspect/graph power view** over the same specimen, not a second model.
- [ ] **Step 5: Verify switching view depth does not mutate review/payment/proof state** and commit.

### Task 5: Legal-term and Wiki/Wikidata context drill-in

**Files:**
- Create in ITIR-suite: `itir-svelte/src/lib/proof/legalTermContext.ts`
- Create in ITIR-suite: `itir-svelte/src/lib/proof/legalTermContext.test.ts`
- Reuse existing revision-locked Wiki/Wikidata review/source-follow interfaces in ITIR-suite.

**Interfaces:**
- Consumes: selected term/entity + canonical context/source trails.
- Produces: lexical orientation, encyclopedia lead/context, entity identity candidates, Australian legal construction refs, and demand-driven contingent arguments.

- [ ] **Step 1: Add an `estoppel` fixture** proving lexical definition, Wiki context, Australian authority, and matter-specific applicability are separate layers.
- [ ] **Step 2: Implement compact hover/card** for lexical/encyclopedia orientation only.
- [ ] **Step 3: Implement explicit `See Australian legal construction` and `Show contingent arguments` actions**.
- [ ] **Step 4: Verify Wiki/Wikidata context never inherits legal authority or payment** and commit.

### Task 6: Flagship end-to-end Mabo proposition specimen

**Files:**
- Create: `tests/fixtures/mabo/flagship_proposition_specimen.*` using the repository's existing non-JSON fixture convention for the production-facing path.
- Create: `tests/pnf/test_mabo_flagship_explanation.py`
- Reuse: `run_slr_mabo_proof_graph.sh` and the existing bounded SLR recurrence.

**Interfaces:**
- Consumes: one existing Mabo proposition chain already represented by repository algebra/parsing.
- Produces: one auditable explanation with source/proof drill-down and either a paid or explicit residual state.

- [ ] **Step 1: Freeze the selected proposition chain and expected role/source boundaries**.
- [ ] **Step 2: Run the thin SLR profile** to acquire/reacquire only the missing source coordinates.
- [ ] **Step 3: Apply explicit SensibLaw review/payment**; do not allow SLR acquisition alone to promote the legal proposition.
- [ ] **Step 4: Render Explain and Inspect projections** from the same specimen.
- [ ] **Step 5: Verify a lay reader can answer what changed/why/what supports it/what limits it/what remains unresolved, and an expert can reopen exact source/proof coordinates**.
- [ ] **Step 6: Commit**.

### Task 7: Formal parity and regression

**Files:**
- Existing: `DASHI/Interop/SensibLawMaboProgressiveExplanationProjectionExact.agda`
- Modify as runtime contracts become exact: the same owner rather than creating a second UI calculus.
- Modify: `DASHI/Interop/Everything.agda`

**Interfaces:**
- Consumes: exact runtime tags/projection/payment behavior from Tasks 1-6.
- Produces: query-indexed adequacy witnesses and authority/progressive-disclosure firewalls.

- [ ] **Step 1: Add exact runtime field/tag parity only after the corresponding runtime surface exists**.
- [ ] **Step 2: Type-check the focused owner**.
- [ ] **Step 3: Run the narrow UI/runner regressions**.
- [ ] **Step 4: Record certification separately from semantic/legal status**.
- [ ] **Step 5: Commit**.