# Ontology Tagging

Current as of 18/11/2025
# Ontology Architecture & Tagging

This document describes the SensibLaw ontology: the structured world-model used
to represent normative sources, legal wrongs, protected interests, harms, and
value frames. It also documents the legacy keyword-based taggers (`lpo.json`,
`cco.json`) that remain part of the rule-ingestion pipeline.

SensibLaw’s ontology is organised into **three layers**:

1. **Normative Systems & Sources (Layer 1)**
2. **Wrong Types, Interests & Values (Layer 2)**
3. **Events, Harms & Remedies (Layer 3)**

The ontology provides stable identifiers for concepts across case law, statutes,
tikanga/customary sources, international human-rights instruments, and
religious/legal traditions.

---

# 1. Layer 1 — Normative Systems & Sources

Layer 1 models *where rules come from*, across all legal traditions, including:

- **LegalSystem**  
  (e.g. `AU.COMMON`, `AU.STATE.QLD`, `NZ.TIKANGA`, `PK.ISLAM.HANAFI`,
  `UN.CRC`, `EU.GDPR`, `US.STATE.CA`)

- **NormSourceCategory**  
  (`STATUTE`, `REGULATION`, `CASE`, `TREATY`, `CUSTOM`, `RELIGIOUS_TEXT`,
  `COMMUNITY_RULE`)

- **LegalSource**  
  A specific document containing rules (e.g. “Family Law Act 1975 (Cth)”, “NTA
  1993 s223”, “[1992] HCA 23 (Mabo)”, “He Whakaputanga”, “Quran Surah 24”).

Every extracted `RuleAtom` produced by the NLP pipeline is linked to its
`LegalSource` and `LegalSystem`.

---

# 2. Layer 2 — Wrong Types, Interests & Values

Layer 2 describes *what the rule regulates or protects*. It includes:

## WrongType

A structured representation of an actionable wrong or norm such as:

- `negligence`
- `economic_abuse_intimate_partner`
- `mana_harm`
- `defamation_reputation`
- `child_exploitation`
- `data_breach_privacy`
- `sacred_site_desecration`

Each `WrongType` is defined by a set of constraints:

- **ActorClass constraints**  
  (e.g. “state actor”, “intimate partner”, “parent/guardian”, “community elder”)

- **ProtectedInterestType mappings**

- **MentalState**  
  (`STRICT`, `NEGLIGENCE`, `RECKLESSNESS`, `INTENT`, or mixed)

- **ValueFrames**  
  (`gender_equality`, `tikanga_balance`, `religious_modesty`,
  `child_rights`, `queer_autonomy`, etc.)

---

## ProtectedInterestType

Interests are *faceted* into three components:

- `subject_kind` (who is protected)  
  (`INDIVIDUAL`, `CHILD`, `GROUP`, `COMMUNITY`, `ENVIRONMENT`, `ANCESTORS`)

- `object_kind` (what aspect)  
  (`BODY`, `MIND`, `PROPERTY`, `DATA`, `REPUTATION`, `STATUS_MANA`,
   `CULTURE`, `TERRITORY`, `ECOSYSTEM`, `FAMILY_RELATIONSHIP`, etc.)

- `modality` (how the interest is protected)  
  (`INTEGRITY`, `USE_AND_ENJOYMENT`, `CONTROL`, `PRIVACY`, `HONOUR_MANA`,
   `DEVELOPMENT`, `NON_DOMINATION`)

A `WrongType` may protect multiple interests.

---

## ValueFrame

ValueFrames describe the *moral or cultural justification* behind a wrong or
remedy, for example:

- `gender_equality`
- `tikanga_balance`
- `patriarchal_modesty`
- `child_rights`
- `religious_morality`
- `queer_autonomy`
- `ecological_stewardship`

ValueFrames allow the system to recognise when two rules serve the same
underlying purpose even across different legal traditions.

---

# 3. Layer 3 — Events, Harms & Remedies

This layer describes *what happened* and *how it relates to the ontology*.

- **Event**  
  A real-world occurrence (argument, transaction, injury, removal of a child,
  sacred-site interference, etc.)

- **HarmInstance**  
  A link between an Event and a ProtectedInterestType (e.g. “this event harmed
  the child’s development and safety”)

- **Event–WrongType links**  
  The classification of an event as a potential wrong.

- **RemedyModality**  
  (`MONETARY`, `LIBERTY_RESTRICTION`, `STATUS_CHANGE`, `SYMBOLIC`,
   `RESTORATIVE_RITUAL`, `STRUCTURAL`, etc.)

This layer supports both TiRC integration and SensibLaw’s reasoning/graph engine.

---

# 4. Keyword-Based Ontology Tagging (Legacy)

SensibLaw includes a lightweight keyword tagger for backward compatibility with
older tools and shallow document classification.

Two keyword ontologies are bundled:

- **lpo.json** — Legal Principles Ontology  
- **cco.json** — Commercial Customs Ontology

Each ontology is a simple dictionary:

```json
{
  "fairness": ["fair", "unfair", "equitable"],
  "environmental_protection": ["environment", "ecology"]
}
```

Below is a **full analysis** of how your existing `ontology.md` diverges from the new, expanded ontology spec—**and a proposed rewritten version** that fits the new model while preserving backwards-compatible keyword tagging.

---

# ✅ Part 1 — Analysis: Where `ontology.md` Diverges from the New Spec

Your current `ontology.md` describes an extremely **lightweight, keyword-based tagger**:

* It only supports **two small ontologies**:

  * `lpo.json` (Legal Principles Ontology)
  * `cco.json` (Commercial Customs Ontology)
* Each ontology is **flat**: `tag_name → [keywords]`
* The tagger attaches `principles` and `customs` to a `Provision` based only on substring matching.

This is **radically narrower** than the ontology described in the new spec (your PDF summary) and the expanded database design.

---

## 🔥 Divergence Summary

### 1. **Spec requires three ontology layers**

The new spec requires modelling:

### **Layer 1 — Normative Systems & Sources**

* LegalSystem
* NormSourceCategory
* LegalSource (Act, case, treaty, tikanga, religious source)
* Provision → LegalSource link

**Your current ontology.md does not mention any of these.**

---

### 2. **Spec requires Layer 2 — Wrong Types & Protected Interests**

Includes:

* WrongType
* ProtectedInterestType
* ActorClass
* RoleMarker
* RelationshipKind
* MentalState
* ValueFrame
* ValueDimension
* CulturalRegister
* WrongType–Source patterns
* WrongType–Interest mappings

**None of these appear in your current ontology documentation.**

Your current tagging supports only keyword-driven “principles” and “customs”.

---

### 3. **Spec requires Layer 3 — Event → Harm modelling**

Includes:

* `Event`
* `HarmInstance`
* Event–WrongType links
* Event → ProtectedInterestType links

Again, **no event/harm ontology appears in ontology.md**.

---

### 4. **Taxonomy structure is flat instead of faceted**

Spec states that interests and wrongs must be faceted:

* interest.subject_kind
* interest.object_kind
* interest.modality
* wrong_type.actor_constraints
* wrong_type.protected_interests
* wrong_type.value_frames
* wrong_type.legal_source_mappings

The current ontology only supports:
**`tag_name → [keywords]`**

---

### 5. **Ontology.json is replaced by multiple ontology tables**

Spec says we will maintain structured tables:

* LegalSource
* WrongType
* ProtectedInterestType
* ValueFrame
* CulturalRegister
* ActorClass
* RoleMarker
* RelationshipKind
* NormSourceCategory
* RemedyModality

Current ontology.md mentions only `lpo.json` and `cco.json`.

---

### 6. **Ontology Tagging must extend beyond provisions**

Spec requires tagging for:

* events (TiRC)
* harms (SensibLaw)
* actors (ActorClass)
* wrongs (WrongType)
* interests/value frames
* multiple legal traditions (AU, Tikanga, Islamic, CRC, EU, US…)

Current ontology.md is only “tag a single provision”.

---

### 7. **Tagger needs to evolve from keyword rules to model-based tagging**

Spec requires hybrid:

* keyword rules
* matcher rules
* dependency/neural classification
* Wikitology-style semantic vectors
* WrongType candidate inference

Current ontology.md documents only a **substring keyword lookup**.

---

# 📌 Conclusion

Your existing `ontology.md` is now **one very small corner** (“keyword tagging utilities”) of a much larger ontology system.

It needs to be rewritten to:

1. Reflect the **three-layer ontology architecture**
2. Place the `lpo`/`cco` taggers as the **legacy/RuleAtom-level ontology helpers**
3. Introduce the real ontology entities (LegalSystem, WrongType, ProtectedInterestType…)
4. Show how NLP inference maps extracted clauses into the ontology

The tagger extracts these keywords from raw text to provide quick, shallow
semantic hints.

## Usage

```python
from ontology.tagger import tag_text

prov = tag_text("Fair business practices protect the environment.")
print(prov.principles)  # ['fairness', 'environmental_protection']
print(prov.customs)     # ['business_practice']
```

## Ingestion Pipeline Integration

During ingestion, `emit_document` applies the tagger so every `Document` and
`Provision` receives:

* `principles` (from lpo.json)
* `customs` (from cco.json)

These tags may be used as **auxiliary signals** by higher-level classifiers
(ProtectedInterest inference, WrongType candidate inference, etc.)

---

# 5. Evolution Toward Full Ontology Tagging

The lightweight keyword system will remain, but the NLP pipeline is being
extended to perform deep ontology mapping:

* ActorRole → ActorClass
* Syntactic object → ProtectedInterestType
* Clause semantics → WrongType candidates
* Document-level cues → ValueFrames
* Legal references → LegalSource binding

These semantic outputs are stored alongside RuleAtoms and power the reasoning
engine.

---

# 6. Summary

| Layer                | Purpose                       | In Current Code      | Documented Here |
| -------------------- | ----------------------------- | -------------------- | --------------- |
| **Layer 1**          | Norm systems/sources          | Partially (metadata) | Added           |
| **Layer 2**          | WrongTypes, Interests, Values | Not implemented yet  | Added           |
| **Layer 3**          | Events, Harms, Remedies       | Not implemented yet  | Added           |
| **Keyword ontology** | Legacy tagging                | Implemented          | Preserved       |

This updated document defines where the shallow taggers fit inside the full
ontology architecture and prepares the project for the expanded schema defined
in `DATABASE.md`.

```








Here is the older version:





The project includes a lightweight tagging utility that assigns legal
principles and commercial customs to provisions extracted from documents.

## Ontology Definitions

Two simple ontologies are bundled as JSON files under `data/ontology`:

- **lpo.json** – Legal Principles Ontology (LPO)
- **cco.json** – Commercial Customs Ontology (CCO)

Each ontology maps tag names to a list of keywords used for rule-based
matching.

## Tagging Provisions

The function `ontology.tagger.tag_text` creates a :class:`~models.provision.Provision`
from raw text and populates `principles` and `customs` lists based on the
ontology keyword matches.  Existing `Provision` instances can be tagged with
`ontology.tagger.tag_provision`.

```python
from ontology.tagger import tag_text

prov = tag_text("Fair business practices protect the environment.")
print(prov.principles)  # ['fairness', 'environmental_protection']
print(prov.customs)     # ['business_practice']
```

## Ingestion Pipeline Integration

During ingestion, `src.ingestion.parser.emit_document` applies the tagger to
produce `Document` objects whose `provisions` field contains the tagged
content.  Each document currently generates a single provision from its body
text, but the approach can be extended to finer-grained parsing.
