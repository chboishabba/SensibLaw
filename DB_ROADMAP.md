# Database Roadmap

For general roadmap please see [roadmap](docs/roadmap.md). The [DATABSE.md file](DATABASE.md) outlines an outdated but relevant view of SensibLaw's Ontology & Database Design
Specification based on a Three-Layer Ontology Structure - however we have now progressed to 6-layer or more.


Below is a clean, explicit **gap analysis** grounded directly in the documents you uploaded.
Your question: **“Please analyse where our current documentation is diverging from our new spec.”**

According to documents from **18 Nov 2025**, your *current repo documentation* (ROADMAP.md, roadmap.md, DATABASE.md, nlp_pipelines.md) diverges from the newly clarified ontology/spec in **five major ways**:

---

# ✅ 1. **Ontology Layers Missing or Only Partially Represented**

### **What the new spec requires**

The PDF lays out a **three-layer ontology**:

* **Layer 1 – Normative systems & sources**
* **Layer 2 – Wrong Types: roles, interests, mental states**
* **Layer 3 – Events, harms, remedies**

This is explicitly described in the spec summary in the PDF (e.g., LegalSystem hierarchy, WrongType structure, ProtectedInterest, HarmInstance, RemedyModality)

### **Where the repo diverges**

Your current documents focus heavily on:

* **RuleAtoms + provisions**
* **Pipeline mechanics**
* **Document ingestion**

But **none of the repo files actually define**:

* `WrongType`
* `ProtectedInterestType`
* `ValueDimension`
* `CulturalRegister`
* `ActorClass`
* `RelationshipKind`
* `HarmInstance`
* `RemedyModality`

This is explicitly listed as missing in the PDF’s "Summary Table — What to Update"

And confirmed by the ROADMAP.md file which says the ontology is “unmaterialized”

---

# ✅ 2. **No Value / Morality / Cultural Reasoning Layer in Repo Docs**

### **Spec requirement**

The PDF states clearly that a **moral/value justification layer** is required:

* ValueFrame
* CulturalRegister
* Competing value-systems (equality vs patriarchal order vs religious orthodoxy)

The spec requires this to be inserted into:

* **ROADMAP.md**
* **Database roadmap**
* **NLP pipeline**

### **Where repo diverges**

There is **zero mention** of:

* ValueFrames
* Moral justifications
* Cultural registers as first-class reasoning elements

For instance, DATABASE.md describes a ValueDimension/ProtectedInterest design philosophically

…but **nowhere is the ValueFrame layer defined, referenced, or required operationally**.

---

# ✅ 3. **NLP Pipeline Lacks WrongType, ActorClass, Interests, and Event Binding**

The spec says:

> *“Docs only have shallow actor roles… update pipeline to map actors → ActorClass, add WrongType inference, add protected-interest inference.”*

### **Where current nlp_pipelines.md diverges**

Current pipeline describes:

* tokenization
* sentence segmentation
* dependency arcs
* legal NER rules

But there is **no connection between:**

* RuleAtoms → ActorClass
* Clauses → WrongType inference
* Clauses → ProtectedInterestType
* RuleAtoms → LegalSource binding (required by spec)

Current docs still treat clause extraction as the end-point.

The new spec treats it as the **start** of semantic inference.

---

# ✅ 4. **Database Roadmap Missing Most Ontology Tables**

The spec explicitly states the repository is missing:

* LegalSystem
* NormSourceCategory
* LegalSource
* WrongType
* WrongType_Source
* ProtectedInterest
* CulturalRegister
* ActorClass
* RoleMarker
* RelationshipKind
* HarmInstance
* RemedyModality

These missing pieces are shown in the PDF table:

And ROADMAP.md confirms these layers are absent:

The new spec requires all three ontology layers to be implemented before rule atoms are useful.

---

# ✅ 5. **Multi-Jurisdiction Support Not Reflected in Existing Docs**

The spec now requires recognition of:

* AU.COMMON
* AU.STATE.QLD
* PK.ISLAM.HANAFI
* NZ.TIKANGA
* US.STATE
* EU *

### **Where repo diverges**

Current database roadmap treats the system as essentially:

* AU-centric
* Single legal tradition
* No religious/customary law categories

ROADMAP.md only references basic “jurisdiction codes” and does **not** model legal traditions or multiple co-existing normative systems.

---

# 📌 Executive Summary — Divergence Map

| Area                                  | Spec Requirement                                        | Repo State                               | Evidence |
| ------------------------------------- | ------------------------------------------------------- | ---------------------------------------- | -------- |
| **Ontology Layers**                   | Must implement Layer1–3                                 | Only RuleAtoms + docs                    |          |
| **Moral/value layer**                 | ValueFrames, CulturalRegisters, justification reasoning | Not present                              |          |
| **WrongType system**                  | Pattern = roles + interest + harm + mental state        | Not defined                              |          |
| **Protected Interests**               | Must be explicit                                        | Only conceptual narrative                |          |
| **ActorClass, Relationship modeling** | Required                                                | Absent                                   |          |
| **Remedies**                          | Required as structured modal types                      | Not mentioned in repo                    |          |
| **Event–Harm modeling**               | Events must map to harms and wrong types                | Current event schema is opaque           |          |
| **Pipeline actor → ontology mapping** | Must classify actors via ActorClass                     | Pipeline only records ‘party’ + raw role |          |
| **Source binding**                    | RuleAtoms → LegalSource link required                   | Not implemented                          |          |

---

# 🎯 What You Should Do Next (Actionable Fixes)

The spec itself includes an “executable plan” for migration:

### **PHASE 1 — Add Layer 1 (Normative Systems)**

LegalSystem, LegalSource, NormSourceCategory

### **PHASE 2 — Add Layer 2 (Wrong Types)**

WrongType, ProtectedInterest, ActorClass, MentalState

### **PHASE 3 — Add Layer 3 (Events + Harms + Remedies)**

Event, EventParticipant, HarmInstance, RemedyModality

### **PHASE 4 — Update NLP Pipeline**

Add: WrongType inference, ActorClass mapping, Protected-Interest inference

### **PHASE 5 — Update ROADMAP.md**

Add ontology sections + multi-system support


# OLDER VERSION BELOW HERE:


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
