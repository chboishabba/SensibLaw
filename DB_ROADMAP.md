# Database Roadmap

This roadmap translates the current multi-layer ontology into deliverable milestones the engineering team can execute. It removes the prior PDF gap-analysis narrative and instead lists concrete tables, sequencing, and ownership to reach a production-ready schema.

## Milestone 1 — Layer 1: Normative Systems & Sources
*Goal: model the legal universe and source hierarchy that all downstream layers reference.*

**Tables/Entities**
- `LegalSystem` (jurisdiction/tradition codes, date ranges, lineage)
- `NormSourceCategory` (statute, case, regulation, customary, religious, treaty)
- `LegalSource` (system + category + citation metadata, versions)
- `SourceTextSegment` (optional: paragraph/section anchors for binding rule atoms)

**Deliverables**
- SQL migrations for the above tables with primary/foreign keys and uniqueness constraints on `(system, citation)`.
- Seed data covering priority systems (AU.COMMON, AU.STATE.QLD, PK.ISLAM.HANAFI, NZ.TIKANGA, US.STATE, EU).* 
- CRUD endpoints/DAOs for lookup and binding rule atoms to `LegalSource` rows.

**Ownership & Sequencing**
- Owner: Data Engineering.
- Dependencies: none (foundational). Complete before any WrongType or pipeline binding work.

## Milestone 2 — Layer 2: Actors, Roles, and Social Context
*Goal: capture who participates in legal relations and how they are connected.*

**Tables/Entities**
- `ActorClass` (e.g., individual, corporate, state, tribunal, customary authority)
- `RoleMarker` (linguistic/structural cues for actor roles in text)
- `RelationshipKind` (family, contract, fiduciary, governmental, communal)
- `CulturalRegister` (optional: cultural or doctrinal traditions influencing interpretation)

**Deliverables**
- Migrations for the above tables with reference data (controlled vocabularies for roles and relationships).
- Join tables linking `ActorClass` and `RelationshipKind` to `LegalSystem` where applicability differs by system.
- API/query utilities for mapping extracted parties to canonical `ActorClass` values.

**Ownership & Sequencing**
- Owner: Ontology Lead + Data Engineering.
- Dependencies: Milestone 1 (`LegalSystem` foreign keys). Finish before WrongType definitions that rely on actor roles.

## Milestone 3 — Layer 3: Wrong Types & Protected Interests
*Goal: define the core wrongdoing patterns and the interests they implicate.*

**Tables/Entities**
- `ProtectedInterest` (life, bodily integrity, property, privacy, cultural identity, equality)
- `WrongType` (pattern templates referencing actors, interests, mental states)
- `WrongType_Source` (bridge between `WrongType` and `LegalSource` for provenance)
- `MentalState` (intent, recklessness, negligence, strict)

**Deliverables**
- SQL migrations (`schemas/migrations/003_milestone3_wrong_types.sql`) establishing cardinality constraints (e.g., `WrongType` requires at least one `ProtectedInterest`) and referencing Milestone 1–2 tables (`legal_system`, `norm_source_category`, `legal_source`, `cultural_register`) for system-scoped enforcement.
- Seed catalog of priority wrong types per `LegalSystem` with citations and protected interest mappings (`data/ontology/wrong_type_catalog_seed.yaml`).
- Authoring guidance for new WrongTypes (naming, versioning, provenance) co-located with the seed catalog.

**Ownership & Sequencing**
- Owner: Ontology Lead.
- Dependencies: Milestones 1–2. Enables event/harm mapping and remedy selection.

## Milestone 4 — Layer 4: Events, Harms, and Participants
*Goal: represent concrete situations that instantiate wrong types and their consequences.*

**Tables/Entities**
- `Event` (typed by `WrongType`, timestamp, location, jurisdiction)
- `EventParticipant` (join to `ActorClass` with role labels from `RoleMarker`)
- `HarmInstance` (severity, category, link to `ProtectedInterest`)
- `IncidentEvidence` (optional: document pointers supporting the event/harm assertion)

**Deliverables**
- Migrations with cascading rules so `Event` deletion cleans up participants and harms.
- Stored procedures or services to register events and auto-link harms to interests.
- Reporting views for harm counts by system and actor class.

**Ownership & Sequencing**
- Owner: Application Engineering + Data Engineering.
- Dependencies: Milestones 1–3. Must precede remedy modeling so harms can be addressed.

## Milestone 5 — Layer 5: Remedies & Value Frames
*Goal: capture normative justifications and the remedial responses available for harms.*

**Tables/Entities**
- `ValueFrame` (competing values such as equality, order, religious orthodoxy, community harmony)
- `Remedy` (remedy type, modality, eligibility rules)
- `ValueFrame_Remedies` (optional join where remedies are justified by specific value frames)
- `CulturalRegister` linkage (if culture-specific values influence remedy selection)

**Deliverables**
- Migrations for the above tables; ensure `Remedy` references `HarmInstance` and `LegalSystem`.
- Seed library of remedies per system with mapped value frames (e.g., injunction vs compensation vs apology).
- Reasoning hooks for pipelines to suggest remedies based on harms and prevailing value frames.

**Ownership & Sequencing**
- Owner: Ontology Lead + Policy/Domain Expert.
- Dependencies: Milestones 1–4. Complete before exposing remedy suggestions in APIs/UI.

## Milestone 6 — Pipeline & Integration
*Goal: bind NLP and application flows to the ontology tables so data moves through all layers.*

**Deliverables**
- Ingestion services that anchor extractions to `LegalSource` and `ActorClass` (Milestones 1–2).
- Inference layer producing `WrongType`, `ProtectedInterest`, and `Event` records from clause/statement detections (Milestone 3–4).
- Recommendation step that proposes `Remedy` selections and associated `ValueFrame` context (Milestone 5).
- Backfill tasks to migrate existing rule atoms and documents onto the new tables.

**Ownership & Sequencing**
- Owner: Application Engineering + ML/NLP.
- Dependencies: Milestones 1–5. Run after schema is stable; provides end-to-end validation for the new ontology.

## Milestone 7 — Governance & QA
*Goal: ensure the ontology and database remain consistent as systems expand.*

**Deliverables**
- Data quality checks (unique citations per `LegalSource`, referential integrity across layers) wired into CI via `python scripts/validate_integrity.py`.
- Versioning policy for `WrongType`, `Remedy`, and `ValueFrame` updates, with migration/backwards-compatibility rules documented in `docs/ontology_versioning.md`.
- Playbooks for onboarding new legal systems and registering new value frames captured in `docs/onboarding_playbooks.md` and enforced through fixtures/validation tests.

**Ownership & Sequencing**
- Owner: Ontology Lead + Data Engineering.
- Dependencies: Parallel to Milestones 3–6; formalize before production release.

## Execution Notes
- Sequence milestones in order; do not begin Milestone 3 until Milestones 1–2 are merged, etc.
- Maintain a single migration branch per milestone to reduce merge conflicts.
- Each milestone should ship with test fixtures and minimal seed data so downstream teams can integrate immediately.
- Update API/contract documentation as soon as new tables are exposed.

