# Database Roadmap

## Context
SensibLaw's database design aspires to a three-layer ontology spanning normative systems and sources, abstract wrong types, and concrete events with harms.【F:DATABASE.md†L5-L24】【F:DATABASE.md†L858-L892】 The current repository primarily implements a SQLite-backed document versioning store and thin JSON schemas for event ingestion, leaving most of the ontology unmaterialized.【F:src/storage/versioned_store.py†L31-L199】【F:sensiblaw/schemas/event.schema.yaml†L1-L11】 This roadmap compares the as-is state with the specification and lays out the steps to close the gap.

## Where we are
- **Document-centric storage only.** VersionedStore maintains documents, revisions, table of contents entries, provisions, and rule atoms with FTS5 support, but it does not model legal systems, wrong types, harms, or cross-cutting ontology links.【F:src/storage/versioned_store.py†L31-L199】
- **Minimal event payload schema.** The event schema accepts IDs and an opaque story object, without any structure for participants, harms, or wrong type tagging, reflecting the absence of layer 2 and layer 3 entities in persistent storage.【F:sensiblaw/schemas/event.schema.yaml†L1-L11】

## Where we should be
- **Layer 1 foundations.** Relational tables (or graph labels) for `LegalSystem`, `NormSourceCategory`, and `LegalSource`, with IDs used as foreign keys for downstream entities so sources and jurisdictions are explicit and comparable.【F:DATABASE.md†L58-L108】
- **Layer 2 wrongs and interests.** Core entities for `WrongType` plus join tables linking wrongs to their defining sources and protected interests, enabling multi-jurisdictional wrong definitions and value taxonomies (families/aspects, cultural registers).【F:DATABASE.md†L153-L188】【F:DATABASE.md†L190-L260】
- **Layer 3 events and harms.** Event records tied to wrong types with per-bearer harm instances so the system can capture multi-party, multi-interest impacts and integrate TiRCorder narratives into the ontology.【F:DATABASE.md†L858-L976】
- **Remedies and constraints.** Normalized remedy modalities and actor/relationship constraints attached to wrong types to reflect available redress and eligibility rules across systems.【F:DATABASE.md†L840-L856】【F:DATABASE.md†L481-L508】

## Next steps
1. **Schema bootstrap.** Introduce the Layer 1 and Layer 2 tables (legal systems, source categories, legal sources, wrong types, wrong–source links, protected interests, cultural registers) alongside migrations and seed data for known jurisdictions and taxonomies.
2. **Event and harm modeling.** Extend the event schema to capture participants, locations, timestamps, wrong type tags, and harm instances; add corresponding persistence tables and ingestion paths that map TiRCorder payloads into the ontology.
3. **Remedies and constraints.** Model remedy modalities, role markers, actor classes, and wrong-type constraints, wiring them into wrong definitions for eligibility checks and recommendations.
4. **Bridge from documents to ontology.** Add extraction pipelines that link versioned document provisions and rule atoms to `LegalSource` entries and then to `WrongType` records, keeping the existing document store while populating the ontology graph.
5. **Testing and provenance.** Add fixtures and validation rules that assert referential integrity across layers, plus receipts linking ingested events and harms back to source text or recordings for auditability.
