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
- When parser tokens are available, regex/pattern action hits must overlap a
  `VERB|AUX` token span before acceptance (prevents nominalization leaks such as
  `death` -> `die`).
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

### R2a. Parser-First Action Label Selection
**Requirement**
- When parser tokens are available, action labels must be selected from
  lemma+dependency classification over `VERB|AUX` tokens.
- Regex action patterns are fallback-only for parser/classifier miss paths and
  must emit fallback warnings.
- Ambiguous lemmas must resolve by deterministic dependency rules
  (e.g., `commission` + `into` -> `commissioned_into`).
**Status:** Implemented (baseline; classifier-first with guarded fallback)

### R2b. Deterministic Semantic Resource Contract
**Requirement**
- Lexical-semantic resources (WordNet/BabelNet) are allowed only as
  deterministic normalization backbones in the authoritative extraction path.
- Canonical extraction/mapping must not depend on LLM generation.
- Any WSD path used for canonical mapping must be deterministic and
  version-pinned.
- Synset mapping must use explicit profile-provided `synset -> canonical_action`
  maps with deterministic tie-break ordering.
- Canonical synset mapping must be single-action or abstain (no silent choice
  between multiple competing mapped actions).
- If synset mapping abstains due to ambiguity, do not fall back to regex action
  patterns for that sentence (surface fallback would be a semantic coercion).
- Resource version pins must be validated at runtime before semantic mapping is
  enabled.
- Mapping-table pins must be validated:
  - `semantic_version_pins.babelnet_table_sha256`
  - `semantic_version_pins.synset_action_map_sha256`
**Status:** Partially implemented (profile semantic-backbone guard enforces
deterministic/non-generative settings and emits normalized extraction-profile
metadata; synset-backed canonical mapping path still pending)

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
- Currency-aware canonical keys (scale+currency normalized to scientific value + currency unit; no composite scale-currency unit tags).
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
**Status:** Partially implemented (numeric claims now emit expression+surface metadata; bitmask compression/storage model still pending)

# Numeric Ontology Integration

### R10. Canonical Numeric Coalescing
**Requirement**
- Grouped number stitching.
- `%` normalization.
- Compact suffix normalization.
- Canonical key-based coalescing in view.
- Suppress date-only numeric fragments in numeric lanes (month/day/year tokens and
  slash-date fragments belong to temporal anchors, not numeric claims).
- Prevent filtered date-like numeric keys from re-entering step numeric lanes
  during claim-to-step merge.
**Status:** Implemented (scale+currency now canonicalized to scientific value + currency unit; composite scale-currency unit tags removed; month/day and slash-date fragments suppressed from numeric lanes with merge guards)

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
**Status:** Partially implemented (baseline step-scoped role typing + alignment emitted; dependency-based unit recovery now captures quantified heads such as `71 lines` and binds `quantity_of` targets into `applies_to`; claim payload includes normalized numeric parts plus explicit `time_anchor/time_years/time_text`; taxonomy/conflict integration pending)

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
- Use dependency-first epistemic detection for claim-bearing steps
  (communication/attribution clause signals such as clausal complements).
- Allow profile-provided lexical fallback only when dependency signals are absent.
- Avoid extractor-hardcoded epistemic verb tables.
- Mark claim-bearing events explicitly.
- Conflict logic applies only to claim-bearing events.
**Status:** Partially implemented (dependency-first classifier + profile lexical fallback emitted in extractor; nominalized attribution patterns still pending)

# Attribution & Sourcing

### R17. Attribution Layer Separation
**Requirement**
- Separate:
  - attributed_actor
  - reporting_actor
  - source_entity
- Preserve requester lane fidelity:
  - detect requester from dependency/step structure,
  - canonicalize requester labels (no possessive/noise surface),
  - avoid collapsing requester projections to `req:none` when request evidence exists.
- Surface requester coverage diagnostics in projection views:
  - when `req:none` is selected, show `requester_coverage` counters,
  - report missing requester event IDs from extraction output,
  - report current-window request-signal vs requester-match counts so no-request windows are explicit.
- Canonicalize actor/subject labels by stripping leading definite article
  (`the X` -> `X`) in extraction output so subject identity does not fragment
  across article/no-article forms.
- Actor/subject coalescing must follow the dedicated contract
  `SensibLaw/docs/actor_coalescing_contract.md` (deterministic, event/frame
  boundary-safe; no fuzzy merge).
- Evidence must not pollute role lanes.
- Support direct vs reported distinction.
**Status:** Partially implemented (event-level attribution attachments emitted for claim-bearing steps; requester canonicalization + step fallback landed; extractor emits requester coverage counters and AAO-all now surfaces `req:none` window/global diagnostics; full SourceEntity/Attribution ontology integration still pending)

### R18. SourceEntity Modeling
**Requirement**
- Materialize `SourceEntity` objects.
- Track publication date, version, hash.
- Link AAO events to source entities.
- Expose source context in non-role projection lanes:
  - AAO-all should show a Source lane wired from source/provenance labels to action nodes via context edges.
  - Source lane labels should be provenance-oriented (source entity/provider/parser), not role actors.
- Expose extraction lens context in non-role projection lanes:
  - AAO-all should show a Lens lane sourced from extraction profile + event lens tags (claim-bearing/SL lane markers).
- Support respectful rate policy tracking.
**Status:** Partially implemented (extractor emits `source_entity` + `extraction_record`; AAO-all now surfaces Source/Lens lanes via context edges; ontology/storage integration and lane assertion tests pending)

# Anchor Graduation

### R19. Magnitude Anchor Graduation
**Requirement**
- Recurrence threshold (N >= configurable).
- Cross-actor reinforcement.
- Range-boundary reinforcement.

# Revision Harness

### R20. Wikipedia Revision Harness (Read-Only)
**Requirement**
- Support previous-vs-current Wikipedia revision comparison as a bounded
  source-artifact harness.
- Record explicit article revision metadata (`revid`, revision timestamp, URL,
  fetch time) for both compared sides.
- Surface:
  - source-text similarity
  - extraction delta summary
  - local graph-impact summary
  - claim-bearing / attribution delta summary
  - reviewer-facing issue packets
- Treat live revision volatility as reportable signal rather than automatic
  regression failure.
- Keep the harness read-only:
  - no ontology mutation
  - no automatic Wikipedia/Wikidata edits
  - no authority transfer from Wikipedia or Wikidata into canonical local
    ontology rows
**Status:** Implemented (baseline report/CLI harness; live scheduling and richer
review-context joins deferred)
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

### R24. Extractor -> Ontology Mapping Contract
**Requirement**
- Ontology fields must be parser-agnostic and canonical (not raw spaCy/Babel class values).
- Each ontology field used in output must define:
  - extractor source attribute(s),
  - normalization rule,
  - fallback rule.
- Mapping behavior must be deterministic and test-covered.
**Status:** Partially implemented (ActionEvent morphology mapping is now implemented in `src/nlp/ontology_mapping.py` with canonical enum output + tests; numeric/temporal mapping expansion pending)

### R25. Inter-fact Linking and Duplicate Guards
**Requirement**
- Fact rows (`ev:*:f*`) must preserve step-local identity within an event.
- `prev_fact_ids` / `next_fact_ids` must be derived from typed chain edges only
  (`sequence`, `content_clause`, `infinitive_clause`), with non-causal semantics.
- Do not collapse governing/complement fact pairs from the same sentence when
  action lemmas differ.
- Fact coalescing must be event-local and anchor-aware; never cross `event_id`
  boundaries based on sentence text alone.
- Fact timeline projections must remain deterministic and idempotent across
  repeated runs.
**Status:** Partially implemented (fact timelines emit chain-aware crosslinks
and loader-level event-local coalescing keys; dedicated clause-chain regression
fixtures and explicit cross-event guard tests still pending)

# Open Gaps (Actionable)
1. Implement numeric role typing expansion (R11).
2. Materialize temporal entities (R13-R14).
3. Implement conflict logic engine (R15).
4. Add anchor graduation state machines (R19-R20).
5. Complete epistemic verb tagging (R16).
6. Finalize typed edge basis metadata and attribution graph edge projection.
7. Implement frame-scope validator (R22).
8. Formalize Non-Goals section (R23).
9. Complete numeric/temporal extractor->ontology mapping coverage and tests (R24).
10. Harden inter-fact coalescing key + add clause-chain regression tests for
    governing/complement sentence pairs (R25).

# Document Notes
- This is a requirements register, not a schema spec.
- Schema definitions live in ontology docs.
- This register tracks behavior-level guarantees.
