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



Further notes from updated:

You’re mostly solid – the “glue” is coherent – but you’re right that **morality/value frames are under-expressed** and there are a couple of spots I’d tweak for clarity / DRY-ness.

I’ll break this into:

1. Small corrections / refinements to what you’ve got
2. Where & how to surface **morality** more explicitly
3. A couple of DRY tweaks so you don’t double-encode the same idea

---

## 1. Small corrections / refinements

Nothing is catastrophically wrong; it’s more about tightening.

### a) WrongType ↔ ValueFrame (one-to-many, not just one)

In the schema you drafted, `wrong_types` has:

```sql
value_frame_id INTEGER  -- FK → value_frames (dominant justification)
```

I’d *keep* the “dominant” pointer, but also add a proper many-to-many:

```sql
CREATE TABLE wrongtype_valueframes (
    wrong_type_id  INTEGER NOT NULL REFERENCES wrong_types(id),
    value_frame_id INTEGER NOT NULL REFERENCES value_frames(id),
    perspective    TEXT NOT NULL,   -- 'STATE', 'INDIGENOUS', 'RELIGIOUS', 'INTERNATIONAL_HR', 'USER'
    weight         REAL,            -- optional, relative importance
    PRIMARY KEY (wrong_type_id, value_frame_id, perspective)
);
```

Reason: the entire point of your project is “this wrong looks *very different* under AU torts, tikanga, UNCRC, church doctrine, etc”. You’ll regret locking it to a single `value_frame_id`.

You can still keep `wrong_types.value_frame_id` as a convenience “default/predominant in this legal system”.

---

### b) ProtectedInterest ↔ ValueFrame

Protected interests are *strongly* moralised. I’d explicitly allow them to declare which frames they’re grounded in:

```sql
CREATE TABLE protectedinterest_valueframes (
    protected_interest_id INTEGER NOT NULL REFERENCES protected_interest_types(id),
    value_frame_id        INTEGER NOT NULL REFERENCES value_frames(id),
    perspective           TEXT NOT NULL,   -- same pattern as above
    PRIMARY KEY (protected_interest_id, value_frame_id, perspective)
);
```

This is the right place to encode things like:

* `BODILY_INTEGRITY` ← HR frame + common-law frame
* `MANA` ← tikanga / Indigenous value frames
* `FAMILY_HONOUR` ← particular religious or cultural frames

Instead of trying to smuggle it into remedies.

---

### c) Remedy should be clearly “what happens”, not “why”

You already have:

```sql
remedies(
    value_frame_id  INTEGER REFERENCES value_frames(id),
    modality_id     INTEGER REFERENCES remedy_modalities(id),
    purpose_id      INTEGER REFERENCES remedy_purposes(id)
)
```

That’s good; I’d just be explicit in docs:

* **Remedy** = what the system *does* (money, custody order, apology, banishment…)
* **ValueFrame** = why the system feels that’s appropriate.

You can then:

* Link **WrongType → Remedy** (typical responses)
* Link **Remedy → ValueFrame** (what moral story justifies that response)

You already modelled this, it just wants a sentence in the design principles spelling it out.

---

### d) LegalSystem should know its canonical value frames

Your `legal_systems` table is fine structurally, but it’s the obvious place to encode the “dominant moral languages”. I’d add:

```sql
CREATE TABLE legalsystem_valueframes (
    legal_system_id INTEGER NOT NULL REFERENCES legal_systems(id),
    value_frame_id  INTEGER NOT NULL REFERENCES value_frames(id),
    role            TEXT NOT NULL,   -- 'FOUNDATIONAL','INFLUENTIAL','CONTESTED','IMPORTED'
    PRIMARY KEY (legal_system_id, value_frame_id, role)
);
```

That lets you express e.g.:

* `AU.FED` → liberal democracy + human rights + common-law tradition
* `IWI.TIKANGA.X` → mana / tapu / utu / whakapapa value frames
* `NGO.UNHCR` → humanitarian protection frames

Again, the schema isn’t “wrong” without this – but this is exactly the bit you felt missing as “not much about morality”.

---

## 2. Where & how to surface morality explicitly

Right now, morality is **implicit**:

* “ValueFrame exists, but mostly used as an FK on WrongType/Remedy.”

I’d make it explicit in three places:

### a) ValueFrame table gets a couple more fields

Something like:

```sql
CREATE TABLE value_frames (
    id             INTEGER PRIMARY KEY,
    code           TEXT NOT NULL UNIQUE,   -- 'HR_DIGNITY', 'TIKANGA_MANA', 'PUBLIC_ORDER', ...
    label          TEXT NOT NULL,
    tradition      TEXT NOT NULL,         -- 'HUMAN_RIGHTS','COMMON_LAW','TIKANGA','RELIGIOUS','USER_PERSONAL'
    source_system  TEXT,                  -- 'UDHR','UNCRC','LocalIwi','Catechism','ICCPR',...
    description    TEXT,
    polarity       TEXT,                  -- 'PROMOTE','AVOID','BALANCE','CONTESTED' (optional)
    is_user_defined INTEGER NOT NULL DEFAULT 0
);
```

This makes the “moral language” first-class:

* A UN CRC frame vs tikanga vs canon law vs user’s own sense of justice are **distinguishable objects**.
* You can line up: “what would UNCRC say about this vs Family Court vs my iwi vs my personal values?”

### b) Attach ValueFrame to *Events* (user’s own moral reading)

Right now, morality only really appears at the **WrongType/Remedy** level (institutional moral stories).

You probably also want a way for the **user’s own view** to be explicit:

```sql
CREATE TABLE event_valueframes (
    event_id       INTEGER NOT NULL REFERENCES events(id),
    value_frame_id INTEGER NOT NULL REFERENCES value_frames(id),
    perspective    TEXT NOT NULL,    -- 'USER','THERAPIST','ADVOCATE'
    weight         REAL,
    PRIMARY KEY (event_id, value_frame_id, perspective)
);
```

Then:

* Event: “my mum yelled at me in court”
* System might not classify it as a legal wrong at all, but **user** can tag it with:

  * `VALUE_FRAME(code='RESPECT_FOR_CHILD')`, perspective `'USER'`
  * An Indigenous frame about respect for elders or balance, etc.

That’s how you avoid the ontology silently taking the state’s side.

### c) Design Principles: explicit morality paragraph

You’re right that the last design-principles block didn’t say much about morality. I’d add a bullet like:

```markdown
- **Moral judgment lives in ValueFrames, not in raw labels.**  
  Table/enum names must remain structural and descriptive (e.g. `HARM_PHYSICAL`, `COURTROOM_UTTERANCE`, `PARENT_TO_CHILD`).  
  Moral evaluation (e.g. “this disrespects mana”, “this offends dignity”, “this is sinful”, “this is unjust”) is encoded via `value_frames` and their links to `wrong_types`, `protected_interest_types`, `remedies`, and (optionally) user-tagged `events`.  
  This lets the same factual pattern be viewed through multiple moral lenses (state law, Indigenous law, human-rights law, religious doctrine, user’s own ethics) without baking any single lens in as “the truth”.
```

That one paragraph in `DATABASE.md` / `ontology.md` makes the intention crystal clear.

---

## 3. Light DRY tweaks

You’re not terribly non-DRY, but a couple of spots can be tightened.

### a) One place for codes; reuse via FK

You currently have lots of `code TEXT NOT NULL UNIQUE` columns (`wrong_types.code`, `protected_interest_types.code`, `value_frames.code`, etc). That’s fine.

Just make sure you **don’t re-encode the same idea twice**:

* If `concepts.code = 'HURT_PHYSICAL'` is the semantic atom, don’t also create a separate `harm_classes.code='HURT_PHYSICAL'`. Use `concept_id` + a looser `code` like `'PHYSICAL'` / `'PHYSICAL_INTEGRITY'` for the harm class. That keeps:

  * “the meaning” (HURT_PHYSICAL) in one place
  * “the legal taxonomy bucket” in another.

### b) Don’t clone “perspective” patterns everywhere: reuse naming

You’re going to have these “perspective” join tables:

* `wrongtype_valueframes`
* `protectedinterest_valueframes`
* `legalsystem_valueframes`
* `event_valueframes`

DRY them conceptually:

* Always use the same `perspective` enum values:

  * `'STATE'`, `'INDIGENOUS'`, `'RELIGIOUS'`, `'INTERNATIONAL_HR'`, `'USER'`, `'OTHER'`.

* In docs, define this once (e.g. `docs/ontology.md` “Perspectives” section) and say all `*_valueframes.perspective` use this enumeration.

You don’t need a shared table for it; just shared semantics.

---

## 4. TL;DR corrections

So, answering your literal question:

> Any corrections? I can't see much about morality in there...

*Structurally* your glue is fine. The key upgrades I’d actually make:

1. **Morality:**

   * Enrich `value_frames` with `tradition` / `source_system`.
   * Add `*_valueframes` join tables for `wrong_types`, `protected_interest_types`, `legal_systems`, and optionally `events`.
   * Add a design-principles bullet that says explicitly: *moral evaluation lives in ValueFrames; everything else stays neutral/structural*.

2. **Perspective handling:**

   * Standardise a `perspective` field where we attach frames (`STATE`, `INDIGENOUS`, `RELIGIOUS`, `INTERNATIONAL_HR`, `USER`…).

3. **DRY semantics:**

   * Avoid duplicating semantic codes; let `concepts.code` be the semantic atom and link to it via `concept_id` from `wrong_elements`, `harm_classes`, etc.

If you’d like, I can now:

* Rewrite the **ValueFrames & Remedies** section of `ontology.md` to reflect this multi-perspective moral story, or
* Draft a **worked example**: one factual pattern (“adult man marries multiple wives in jurisdiction X”) viewed as (a) legal wrong in AU family law, (b) religiously endorsed, (c) HR-problematic, all using these ValueFrame links.
