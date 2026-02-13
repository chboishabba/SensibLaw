# Wiki Timeline Requirements Register (Thread `698e95ec-1154-83a0-b40c-d3a432f97239`)

> Note: Active implementation tracking now lives in
> `docs/wiki_timeline_requirements_v2_20260213.md`. This thread register is
> retained as provenance + historical trace mapping.

## Purpose
Capture the concrete requirements discussed in the robust context thread and map them to current implementation status in SensibLaw/itir-svelte.

This is a requirements trace artifact (not a behavior contract by itself).

## Scope
- Wikipedia timeline extraction (`scripts/wiki_timeline_extract.py`)
- AAO extraction (`scripts/wiki_timeline_aoo_extract.py`)
- Timeline/AAO graph rendering (`itir-svelte/src/routes/graphs/*`)
- Numeric + temporal modeling direction for SL ontology integration

## Requirement Register

### R1. Action extraction must be verb-led in legal narrative lanes
- Requirement:
  - Action head must be verb lemma from dependency parsing.
  - Disable noun-action fallback in legal narrative lanes.
  - If no verb exists, allow null/fragment instead of noun invention.
- Status: **Partially implemented**
  - Verb gating and parser-first fallback are in place.
  - Legacy sentence-family overrides still exist in extractor.
- Evidence:
  - `scripts/wiki_timeline_aoo_extract.py` (action extraction + profile config)
  - `tests/test_wiki_timeline_no_semantic_regex_regressions.py`

### R2. Split every finite verb but classify step types
- Requirement:
  - Emit clause/verb progression deterministically.
  - Distinguish types like `JUDICIAL_ACT`, `PARTY_ARGUMENT`, `FACTUAL_ACT`, `CLAUSE_MECHANIC`, `AUXILIARY`.
- Status: **Pending**
  - Multi-step extraction exists.
  - Explicit step-type taxonomy is not yet emitted as a stable field.

### R3. Passive role normalization
- Requirement:
  - Normalize passive clauses so logical actor/object are consistent (`agent` vs `nsubjpass`).
- Status: **Partially implemented**
  - Dependency-first passive agent extraction exists, with regex fallback warning.
  - Full truth-layer passive role normalization contract remains pending.
- Evidence:
  - `scripts/wiki_timeline_aoo_extract.py` (`_extract_passive_agents_from_doc`, fallback warnings)

### R4. Truth/view separation for objects
- Requirement:
  - Preserve truth lanes separately (`entity_objects`, `modifier_objects`), hide modifiers by default in view.
- Status: **Implemented (core)**
- Evidence:
  - Extractor emits lanes.
  - Graph views prioritize entity objects and keep modifier content separate.

### R5. EventFrame temporal model
- Requirement:
  - Time attaches to frame/event anchor, not every step.
  - Step sequence is textual linearization (`NEXT_STEP`), not causation.
- Status: **Partially implemented**
  - Anchors are frame-level and sequence edges are linearized in UI.
  - Explicit `EventFrame` schema object + typed `NEXT_STEP` semantics contract not fully materialized.

### R6. Frame-scoped projection invariants
- Requirement:
  - No “date -> action -> everything in corpus” leakage.
  - Context/render must be frame/event scoped.
- Status: **Partially implemented**
  - Object projection tightened to step/event scope.
  - Dedicated scope validator remains pending.
- Evidence:
  - `todo.md` has explicit scope validator TODO.

### R7. Evidence/attribution layer separation
- Requirement:
  - Evidence/source/context must not pollute role lanes.
  - Use typed support/attribution links.
- Status: **Partially implemented**
  - Evidence lanes/overlays exist in views.
  - Extractor-side typed frame classes/edge basis still pending.

### R8. Regex minimization boundary
- Requirement:
  - Dependency/token-first for semantic extraction.
  - Regex only for date/citation/hygiene and explicit fallbacks with warnings.
- Status: **Partially implemented**
  - Numeric lane aligned to parser-first with regex fallback.
  - Remaining semantic regex debt is tracked (request/legacy sentence family branches).
- Evidence:
  - `todo.md` text-method inventory and de-regex backlog

### R9. Numeric canonical identity and coalescing
- Requirement:
  - Canonical key-based coalescing in views.
  - Grouped number stitching; `%` normalization.
  - Currency-aware keys where explicit markers exist.
- Status: **Implemented (current slice)**
- Evidence:
  - Extractor keying and mention normalization
  - AAO/AAO-all numeric key node mapping
  - tests for grouped values and currency (`$5.6trillion -> 5.6|trillion_usd`)

### R10. Time precision display consistency
- Requirement:
  - Context rows should display event anchor precision (day/month/year), not bucket-downcast.
- Status: **Implemented**
- Evidence:
  - `itir-svelte/src/routes/graphs/wiki-timeline-aoo-all/+page.svelte` context row time rendering

### R11. Temporal ontology integration with broader numeric ontology
- Requirement:
  - Formalize `TimePoint`, `TimeInterval`, `TimeDuration`.
  - Integrate with quantified claim conflict logic.
- Status: **Design documented, implementation pending**
- Evidence:
  - Numeric ontology doc includes forward integration notes.
  - No materialized temporal claim objects yet in payload/schema.

### R12. Claim abstraction vs implicit AAO claims
- Requirement:
  - Explicitly decide whether AAO action rows are sufficient claim carriers for now.
- Status: **Decided for now**
  - Current direction keeps AAO as implicit claim structure.
  - Explicit claim entity deferred.

### R13. Cross-time event mention lane (non-synthetic)
- Requirement:
  - Preserve referenced global events as mention overlays; do not synthesize timeline rows.
- Status: **Partially implemented**
  - Mention anchors exist (`kind=mention`, including special Sep 11 matching).
  - Dedicated `MENTIONS_EVENT` overlay edges still pending.

### R14. Source follow surfacing + respectful legal-source pacing
- Requirement:
  - Surface follow providers (`austlii`, `jade`, `wikipedia`, etc).
  - Respectful legal/wiki request pacing and explicit rate policy.
- Status: **Implemented (current operations slice)**
  - Follow hints emitted in context.
  - Source-pack scripts include explicit per-host pacing defaults.

### R15. Identity and non-coercion contract (numeric + temporal)
- Requirement:
  - Numeric identity must be formatting-invariant and unit-aware.
  - Temporal identity must preserve source granularity (year/month/day).
  - No silent precision inflation (`5.6 trillion` -> fake exact integer) or time downcast/upcast coercion.
- Status: **Partially implemented**
  - Numeric identity contract exists.
  - Temporal non-coercion is not yet formalized as a schema-level invariant.
- Evidence:
  - `docs/numeric_representation_contract_20260213.md`
  - `itir-svelte/src/routes/graphs/wiki-timeline-aoo-all/+page.svelte` (anchor precision display)

### R16. Claim-bearing event classification
- Requirement:
  - Explicitly classify claim-bearing events (epistemic verbs / assertion frames) vs factual acts.
  - Conflict/compatibility checks must run only on claim-bearing lanes.
- Status: **Pending**
  - AAO currently treats claims implicitly via action rows.
  - No stable claim-bearing field exists yet.

### R17. Quantified conflict/compatibility tri-state
- Requirement:
  - Implement deterministic `conflict` / `consistent` / `underdetermined` outcomes.
  - Conflict requires both temporal overlap and numeric non-overlap for same bound subject scope.
  - Projection-vs-actual containment must not be marked as conflict.
- Status: **Pending**
  - Design intent documented.
  - No production conflict engine yet.

### R18. Anchor graduation rules
- Requirement:
  - Define deterministic graduation for `Magnitude` and `TimePoint` anchors.
  - Use recurrence and cross-actor/reference thresholds.
  - Keep graduation reversible/auditable.
- Status: **Pending**
  - Discussed in thread and ontology notes, not implemented.

### R19. Typed edge basis metadata
- Requirement:
  - Every non-role edge must carry explicit basis metadata (e.g., `ccomp`, `xcomp`, `citation_overlap`, `paragraph_adjacent`).
  - `NEXT_STEP` must be explicit sequence-only (non-causal) edge type.
  - `MENTIONS_EVENT` must be typed as non-synthetic/non-causal.
- Status: **Pending**
  - Partial edge typing exists in views.
  - Basis metadata contract not emitted end-to-end.

### R20. Granularity-safe temporal comparison
- Requirement:
  - Temporal comparison/overlap must respect granularity (`year` != `day`).
  - No implicit calendar boundary assumptions hidden from payload.
- Status: **Pending**
  - Precision-preserving display exists.
  - Comparison logic and schema are not yet materialized.

### R21. Numeric semantic role typing + verb alignment
- Requirement:
  - Numeric mentions must bind to governing verb step and semantic role (`transaction_price`, `investment`, `rate`, `count`, `percentage_of`, etc.).
  - Multi-verb sentences must not flatten all numerics under a single action.
  - Distinguish structurally different monetary roles in one sentence (e.g., transaction price vs personal investment).
- Status: **Partially implemented**
  - Step-scoped `numeric_claims` with parser-first step alignment and minimal role taxonomy are now emitted.
  - Coverage currently focuses on deterministic baseline roles (`transaction_price`, `personal_investment`, `revenue`, `cost`, `rate`, `count`, `percentage_of`).
  - Full ontology-level claim materialization and broader role coverage remain pending.
- Evidence:
  - `scripts/wiki_timeline_aoo_extract.py` (`numeric_claims` emission + role/alignment helpers)
  - `tests/test_wiki_timeline_numeric_lane.py` (role inference + multi-verb alignment test)

### R22. Date extraction fidelity (event anchor derivation)
- Requirement:
  - Capture explicit dates from sentence text and bounded heading fallbacks.
  - Preserve strongest available anchor precision in extracted event rows.
  - Avoid synthetic narrative row invention when only references are present.
- Status: **Partially implemented**
  - Heading fallback + mention anchors are implemented.
  - Some user-observed cases still miss expected day-level extraction in event context lanes.
- Evidence:
  - `scripts/wiki_timeline_extract.py` (heading/mention anchors)
  - user examples in thread (`June 10, 2007`, `September 11` references)

### R23. Coalescing boundary contract (strict, deterministic)
- Requirement:
  - Entity/action/frame/evidence coalescing must be ID- and anchor-aware.
  - No fuzzy/string-similarity/embedding merges in truth layer.
  - Distinguish truth-layer coalescing from view-layer grouping.
- Status: **Partially implemented**
  - Deterministic coalescing hardening exists for current AAO slices.
  - Full boundary contract coverage across evidence/time layers remains pending.

### R24. Optional content moderation projection layer (view-only)
- Requirement:
  - Support policy-controlled display transforms (CMP/CMPL) without mutating canonical AAO truth data.
  - Keep stable IDs and canonical lemmas intact.
- Status: **Pending**
  - Discussed and designed in thread.
  - Not implemented in wiki timeline views.

### R25. Epistemic-neutral UI rendering contract
- Requirement:
  - Separate structural role edges from evidence/context overlays.
  - Distinguish entity vs modifier lanes visually.
  - Provide scope/profile badges to prevent implicit endorsement cues.
- Status: **Partially implemented**
  - Basic lane separation exists.
  - Full neutral visual contract and toggles are pending.

### R26. Validation and CI invariants coverage
- Requirement:
  - Add explicit invariants for:
    - no semantic regex reintroduction,
    - frame-scope leakage,
    - container-verb suppression (`have` + `xcomp`),
    - non-verb action rejection,
    - numeric grouped-prefix bleed prevention.
- Status: **Partially implemented**
  - Semantic regex and numeric-lane regressions are covered.
  - Scope validator and several structural invariants are still missing.

### R27. Explicit non-goals boundary
- Requirement:
  - Document non-goals for this slice (no synthetic timeline reconstruction, no probabilistic belief update, no hidden causal inference, no silent precision coercion).
- Status: **Partially implemented**
  - Non-goal language exists in multiple docs.
  - Not centralized in this register yet.

### R28. Sourcing and attribution ontology layer
- Requirement:
  - Materialize explicit sourcing/attribution structures:
    - `SourceEntity` (artifact provenance),
    - `Attribution` (claim-level source attribution),
    - `ExtractionRecord` (machine provenance).
  - Keep actor-of-content vs reporting-actor vs source-entity distinct.
- Status: **Design documented, implementation pending**
- Evidence:
  - `docs/sourcing_attribution_ontology_20260213.md`
  - Existing extractor attribution modifiers (`communication_verbs` profile path) indicate partial precursor behavior.

### R29. Attribution-aware conflict evaluation
- Requirement:
  - Conflict/compatibility outputs must preserve attribution context (attributed actor, reporting actor, source entity).
  - Attribution metadata must not pollute AAO role lanes.
- Status: **Pending**
  - No attribution-aware conflict engine is materialized yet.

## Open Gaps (Actionable)
1. Implement explicit step/frame typing fields plus claim-bearing classification (`R2`, `R16`).
2. Implement frame-scope validator in timeline projections and fail loudly in dev/test (`R6`, `R26`).
3. Complete de-regex pass for remaining semantic sentence-family branches (`R8`).
4. Materialize temporal claim entities (`TimePoint`/`TimeInterval`/`TimeDuration`) and granularity-safe comparison semantics (`R11`, `R20`).
5. Add non-synthetic `MENTIONS_EVENT` overlay edges in graph payload/view with typed basis metadata (`R13`, `R19`).
6. Implement quantified conflict/compatibility tri-state engine with temporal-overlap gating (`R17`).
7. Expand numeric semantic role typing coverage (taxonomy breadth + conflict integration) beyond current baseline step-aligned implementation (`R21`).
8. Add deterministic anchor graduation state machine for numeric/time anchors (`R18`).
9. Implement optional CMP/CMPL view projection layer without truth mutation (`R24`).
10. Consolidate explicit non-goals into this register and CI docs (`R27`).
11. Implement sourcing/attribution model objects and deterministic id helpers (`R28`).
12. Add attribution-aware conflict result metadata for quantified comparisons (`R29`).

## Completeness Audit (Thread Coverage)
Requirement families surfaced in thread and now captured here:
- Extraction structure: `R1..R8`
- Numeric identity/coalescing: `R9`, `R15`, `R21`, `R23`
- Temporal precision/modeling: `R10`, `R11`, `R20`, `R22`
- Claim/evidence/attribution: `R7`, `R12`, `R16`, `R19`
- Cross-time event references: `R13`, `R22`
- Source operations/pacing: `R14`
- Sourcing/attribution ontology: `R28`, `R29`
- UI/view neutrality + moderation projection: `R24`, `R25`
- Validation/non-goals/discipline: `R26`, `R27`

## Architecture Gap Closure Matrix (10-point review)
This matrix maps the explicit architecture review checklist into requirement ids.

1. Identity & non-coercion contract
   - Coverage: `R15`, plus related implementation slice in `R9`/`R10`.
   - Status: Partially implemented.
2. Claim-bearing event classification
   - Coverage: `R16`.
   - Status: Pending.
3. Quantified conflict/compatibility logic
   - Coverage: `R17`.
   - Status: Pending.
4. Anchor graduation rules
   - Coverage: `R18`.
   - Status: Pending.
5. Typed edge basis metadata
   - Coverage: `R19`.
   - Status: Pending.
6. Granularity-safe temporal comparison
   - Coverage: `R20`.
   - Status: Pending.
7. Ratio/range structured numeric modeling
   - Coverage: numeric ontology contract (`RangeClaim`/`RatioClaim`) and execution backlog in `R21` + TODO numeric ontology v0.1.
   - Status: Baseline numeric role alignment implemented; full ontology materialization pending.
8. Attribution ontology registration
   - Coverage: `R28` and `R29`.
   - Status: Design documented; conflict integration pending.
9. Validation hard-fail scope layer
   - Coverage: `R26` and open gap #2.
   - Status: Partially implemented (tests exist), scope hard-fail validator pending.
10. Explicit non-goals
   - Coverage: `R27`.
   - Status: Partially implemented (documented, centralization still pending).

## Notes on Context Provenance
- Thread resolution path:
  - DB-first lookup miss
  - Live fetch used to recover canonical conversation content earlier in session
  - Later rerun encountered DNS/network fallback error under restricted network
- Context artifacts saved under `__CONTEXT/last_sync/`.
