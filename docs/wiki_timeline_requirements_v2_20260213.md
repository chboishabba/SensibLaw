# Wiki Timeline Requirements Register (v2)

**Thread Origin:** `698e95ec-1154-83a0-b40c-d3a432f97239`  
**Doc Type:** Requirements Trace Artifact  
**Status:** Living Architecture Contract
**Canonical Register:** this v2 document is the active requirements register for
implementation tracking. The earlier thread-trace register
(`docs/wiki_timeline_requirements_698e95ec_20260213.md`) is retained for
provenance and historical mapping.

## Scope
- Wikipedia timeline extraction (`scripts/wiki_timeline_extract.py`)
- AAO extraction (`scripts/wiki_timeline_aoo_extract.py`)
- Timeline/AAO graph rendering (`itir-svelte/src/routes/graphs/*`)
- Numeric + temporal ontology integration
- Attribution / sourcing layer
- Frame-scoped projection invariants

# Core Extraction Requirements

### R1. Verb-Led Action Extraction (Legal Narrative Mode)
**Requirement**
- Action head must be verb lemma from dependency parsing.
- Disable noun-action fallback in legal narrative lanes.
- If no finite verb exists, emit fragment/null instead of inventing action.
**Status:** Partially implemented

### R2. Deterministic Step Emission + Step Typing
**Requirement**
- Emit every finite verb deterministically.
- Classify step types:
  - `JUDICIAL_ACT`
  - `PARTY_ARGUMENT`
  - `FACTUAL_ACT`
  - `CLAUSE_MECHANIC`
  - `AUXILIARY`
- Step type must be stable field in payload.
**Status:** Pending

### R3. Passive Role Normalization
**Requirement**
- Normalize passive clauses into logical actor/object.
- Prefer dependency parsing (`agent`, `nsubjpass`).
- Regex fallback allowed only with warning.
**Status:** Partially implemented

### R4. Truth/View Separation
**Requirement**
- Preserve `entity_objects` vs `modifier_objects`.
- UI hides modifiers by default.
- Truth-layer lanes remain distinct.
**Status:** Implemented

# Event & Frame Model

### R5. Explicit EventFrame Model
**Requirement**
- Time attaches to frame anchor, not individual steps.
- `NEXT_STEP` is textual linearization only.
- Define explicit `EventFrame` schema object.
- Typed `NEXT_STEP` edges.
**Status:** Partially implemented

### R6. Frame-Scoped Projection Invariants
**Requirement**
- No cross-frame object leakage.
- Context/render must remain frame-scoped.
- Implement frame-scope validator that fails loudly in dev/test.
**Status:** Partially implemented

# Identity & Invariance Contracts

### R7. Numeric Identity Invariance Contract
**Requirement**
- Canonical magnitude identity independent of formatting.
- No integer-expansion precision inflation.
- Currency-aware canonical keys.
- Deterministic canonical ID function.
**Status:** Implemented (current slice)

### R8. Temporal Identity & Granularity Contract
**Requirement**
- Preserve granularity (year/month/day/quarter).
- No silent downcasting or upcasting.
- No coercion of year -> day.
- Deterministic TimePoint ID.
**Status:** Design documented, implementation pending

### R9. Formatting Phenotype Separation
**Requirement**
- Formatting must not affect identity.
- Store format as bitmask/flags.
- Surface regeneration deterministic.
- Avoid duplicate raw string storage.
**Status:** Partially implemented

# Numeric Ontology Integration

### R10. Canonical Numeric Coalescing
**Requirement**
- Grouped number stitching.
- `%` normalization.
- Compact suffix normalization.
- Canonical key-based coalescing in view.
**Status:** Implemented

### R11. Numeric Role Typing
**Requirement**
- Each numeric must attach to governing verb step.
- Role classification required:
  - `transaction_price`
  - `investment`
  - `revenue`
  - `cost`
  - `rate`
  - `count`
  - `percentage_of`
- Prevent flattening heterogeneous monetary roles.
**Status:** Partially implemented (baseline step-scoped role typing + alignment emitted; taxonomy/conflict integration pending)

### R12. Range & Ratio Structured Modeling
**Requirement**
- Detect and emit `RangeClaim` objects.
- Detect and emit `RatioClaim` objects.
- Do not flatten numerator/denominator into independent numerics.
- Derived percentages optional but not identity-defining.
**Status:** Pending

# Temporal Ontology Integration

### R13. TimePoint / Interval / Duration Modeling
**Requirement**
- Materialize:
  - `TimePoint`
  - `TimeInterval`
  - `TimeDuration`
- Temporal claims attach to EventFrame.
- Support relative expressions (“after X for 4 months”).
**Status:** Design documented, implementation pending

### R14. Granularity-Safe Temporal Comparison
**Requirement**
- Year-level claims must compare as year-intervals.
- Overlap detection must respect granularity.
- No false temporal precision in conflict logic.
**Status:** Pending

# Conflict & Compatibility Logic

### R15. Quantified Conflict Logic
**Requirement**  
Two quantified claims conflict iff:
- Same subject binding.
- Temporal supports overlap.
- Numeric intervals do not overlap.
- Comparable attribution class.

Must classify:
- `conflict`
- `compatible`
- `underdetermined`

Projection containment != conflict.
**Status:** Pending

### R16. Epistemic Verb Classification
**Requirement**
- Maintain list of epistemic verbs:
  - estimated
  - projected
  - reported
  - said
  - claimed
  - found
- Mark claim-bearing events explicitly.
- Conflict logic applies only to claim-bearing events.
**Status:** Pending

# Attribution & Sourcing

### R17. Attribution Layer Separation
**Requirement**
- Separate:
  - attributed_actor
  - reporting_actor
  - source_entity
- Evidence must not pollute role lanes.
- Support direct vs reported distinction.
**Status:** Partially implemented

### R18. SourceEntity Modeling
**Requirement**
- Materialize `SourceEntity` objects.
- Track publication date, version, hash.
- Link AAO events to source entities.
- Support respectful rate policy tracking.
**Status:** Implemented (operations slice), ontology pending

# Anchor Graduation

### R19. Magnitude Anchor Graduation
**Requirement**
- Recurrence threshold (N >= configurable).
- Cross-actor reinforcement.
- Range-boundary reinforcement.
- Maintain anchor state:
  - transient
  - candidate
  - anchor
**Status:** Pending

### R20. TimePoint Anchor Graduation
**Requirement**
- Promote TimePoint to anchor if:
  - Cross-event reference >= threshold.
  - Used as relative reference anchor.
  - Linked to named event.
- Track anchor metadata fields.
**Status:** Pending

# Global Events & Mentions

### R21. Referenced Global Event Overlay
**Requirement**
- Preserve referenced global events as mention overlays.
- Emit typed `MENTIONS_EVENT` edges.
- Do not synthesize timeline rows.
**Status:** Partially implemented

# Validation & Enforcement

### R22. Frame-Scope Validator
**Requirement**
- Enforce no cross-frame projection leakage.
- Dev/test must hard-fail on violation.
- Provide explicit scope error diagnostics.
**Status:** Pending

### R23. Non-Goals Declaration
**Requirement**  
Explicitly state:
- No probabilistic belief updating.
- No automatic rounding-based merging.
- No authority weighting yet.
- No silent precision expansion.
- No revision-chain inference in current slice.
**Status:** Not yet formalized

# Open Gaps (Actionable)
1. Implement numeric role typing expansion (R11).
2. Materialize temporal entities (R13-R14).
3. Implement conflict logic engine (R15).
4. Add anchor graduation state machines (R19-R20).
5. Complete epistemic verb tagging (R16).
6. Finalize typed edge basis metadata.
7. Implement frame-scope validator (R22).
8. Formalize Non-Goals section (R23).

# Document Notes
- This is a requirements register, not a schema spec.
- Schema definitions live in ontology docs.
- This register tracks behavior-level guarantees.
