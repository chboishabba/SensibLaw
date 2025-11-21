# Ontology Architecture & Tagging

Current as of 18/11/2025

SensibLaw's ontology now follows a **Layer‑0 text substrate plus six legal layers (L1–L6)**. This document mirrors the definitions in [`DATABASE.md`](../DATABASE.md) and the relationships shown in [`docs/ontology_er.md`](./ontology_er.md) so downstream teams can rely on a single, consistent architecture. Stable identifiers span normative sources, wrong types, protected interests, harms, value frames, and remedies while remaining compatible with legacy keyword taggers (`lpo.json`, `cco.json`).

## Layer Summary (L0–L6)

| Layer | Scope | Representative Entities |
| --- | --- | --- |
| **Layer 0 — Text & Provenance** | Raw text containers and utterance mapping used for provenance. | `Document`, `Sentence`, `Utterance`, `UtteranceSentence` |
| **Layer 1 — Events & Actors** | Life/legal events and the actors who participate in or trigger them. | `Event`, `Actor`, `EventFinanceLink`, `FinanceProvenance` |
| **Layer 2 — Claims & Cases** | Case/claim scaffolding that organises allegations, issues, and fact sets. | `Case`, `Claim`, `Issue`, `ClaimEvent` |
| **Layer 3 — Norm Sources & Provisions** | Jurisdictions, legal sources, and citations that authorise duties. | `LegalSystem`, `NormSourceCategory`, `LegalSource`, `Provision` |
| **Layer 4 — Wrong Types & Duties** | Abstract wrongs/offences and the doctrinal elements that define them. | `WrongType`, `WrongTypeSourceLink`, `WrongElementRequirement`, `MentalState`, `ActorConstraint` |
| **Layer 5 — Protected Interests & Harms** | What the law protects and how events damage those interests. | `ValueDimension`, `CulturalRegister`, `ProtectedInterestType`, `HarmInstance` |
| **Layer 6 — Value Frames & Remedies** | Moral frames, community perspectives, and outcome modalities. | `ValueFrame`, `RemedyModality`, `EventRemedy`, `Perspective` |

## Layer Details

### Layer 0 — Text & Provenance
- **Document**: canonical container for transcripts, provisions, notes, or reasons.
- **Sentence**: sentence-level slices of documents linked to their parent `Document`.
- **Utterance** and **UtteranceSentence**: diarised speech segments and the ordered mapping of sentences back to the originating utterance.

### Layer 1 — Events & Actors
- **Event**: life/legal/system events with time bounds.
- **Actor**: people, organisations, state entities, or recognised legal persons.
- **EventFinanceLink**: ties events to transactional evidence.
- **FinanceProvenance**: traces sentences that explain a transaction.

### Layer 2 — Claims & Cases
- **Case**: matter-level container with jurisdiction and party metadata.
- **Claim**: asserted cause of action or defence within a case.
- **Issue**: contested questions or doctrinal elements tied to a claim.
- **ClaimEvent**: join table mapping events into the claim fact pattern.

### Layer 3 — Norm Sources & Provisions
- **LegalSystem**: jurisdiction or tradition identifiers (e.g., `AU.COMMON`, `NZ.TIKANGA`).
- **NormSourceCategory**: authority type such as `STATUTE`, `CASE`, `TREATY`, `CUSTOM`, `RELIGIOUS_TEXT`, `COMMUNITY_RULE`.
- **LegalSource**: specific source documents with citation metadata.
- **Provision**: clause-level anchors inside a `LegalSource` with section/paragraph structure.

### Layer 4 — Wrong Types & Duties
- **WrongType**: actionable wrong/offence scoped to a `LegalSystem` and tagged with its primary `NormSourceCategory`.
- **WrongTypeSourceLink**: many-to-many mapping between `WrongType` and `LegalSource` (e.g., `creates`, `defines`, `leading_case`).
- **WrongElementRequirement**: element-level requirements (duty, breach, causation, defences) optionally aligned to `Issue` records.
- **ActorConstraint** and **MentalState**: constrain which actors can commit or be subject to the wrong and the culpability standard required.

### Layer 5 — Protected Interests & Harms
- **ValueDimension**: faceted taxonomy combining family/aspect (e.g., integrity, status, control; body, reputation, information, territory).
- **CulturalRegister**: optional cultural inflections of a value (e.g., `mana`, `face`, `izzat`).
- **ProtectedInterestType**: composed interest definition referencing a `ValueDimension` and, where relevant, a `CulturalRegister`.
- **HarmInstance**: event-level assertion that an interest was harmed, often paired with `ClaimEvent` to show which facts satisfy which protected interests.

### Layer 6 — Value Frames & Remedies
- **ValueFrame**: justificatory frames (e.g., `gender_equality`, `tikanga_balance`, `child_rights`, `ecological_stewardship`).
- **Perspective**: optional qualifier that records whose viewpoint the frame reflects (community, state, victim, accused).
- **RemedyModality**: remedy families (`MONETARY`, `LIBERTY_RESTRICTION`, `STATUS_CHANGE`, `SYMBOLIC`, `RESTORATIVE_RITUAL`, `STRUCTURAL`).
- **RemedyCatalog**: reusable templates for common remedies, keyed to `remedy_modality_id` and localised by legal system or cultural register.
- **EventRemedy**: joins events (or claims) to proposed or ordered remedies and tags them with the applicable `ValueFrame`/`Perspective`.

## Relationships and Sources of Truth
- The ER relationships across text, finance, provenance, and legal layers are illustrated in [`docs/ontology_er.md`](./ontology_er.md).
- Schema snapshots (for example, `schemas/event.schema.yaml`) remain authoritative for serialized payloads.
- [`DATABASE.md`](../DATABASE.md) is the canonical reference for field-level keys, foreign-key wiring, and any future extensions.

## Keyword-Based Ontology Tagging (Legacy)
SensibLaw still ships a lightweight keyword tagger for backward compatibility with older tools and shallow document classification. These taggers remain separate from Layers 0–6 but can be used to seed hints for downstream processing.

Two keyword ontologies are bundled:
- **lpo.json** — Legal Principles Ontology
- **cco.json** — Commercial Customs Ontology

Each ontology is a simple dictionary of keyword lists:

```json
{
  "fairness": ["fair", "unfair", "equitable"],
  "environmental_protection": ["environment", "ecology"]
}
```

When migrating to the layered ontology, preserve these tags for compatibility while favouring `WrongType`, `ProtectedInterestType`, `ValueFrame`, and `EventRemedy` mappings for structured reasoning.
