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
