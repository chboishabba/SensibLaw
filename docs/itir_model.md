# ITIR Data Model (Owned by SensibLaw Layer)

## Purpose

ITIR (Investigative & Interpretive Reasoning) defines the **explicit
interpretation layer** over the SensibLaw (SL) structural substrate.

ITIR objects represent **claims, hypotheses, actors, events, and
relationships** that are:
- non-authoritative
- explicitly attributed
- reversible
- span-backed by SL (TextSpan with revision_id + character offsets)

ITIR never mutates source text or structural spans.
All interpretation remains an overlay.

---

## Core Principle

> **Every ITIR object must cite SL spans (TextSpan).**
> **No interpretation exists without provenance.**

---

## Object Classes

### Claim

A Claim represents an asserted statement about the world.

Claims may be true, false, disputed, or unknown.

**Required fields**
- `claim_id`
- `asserted_by` (user, org, branch)
- `span_refs` (list of `{revision_id, start_char, end_char}`)
- `confidence` (0-1 or enum)
- `created_at`

**Optional**
- `summary` (derived, non-authoritative)
- `notes`

Claims do not imply correctness.

---

### Hypothesis

A Hypothesis is a tentative explanatory model.

Types include:
- `actor`
- `event`
- `motive`
- `timeline`
- `relationship`

**Required**
- `hypothesis_id`
- `type`
- `description`
- `supporting_claims`
- `contradicting_claims`
- `confidence`

Hypotheses may coexist and conflict.

---

### Actor (Hypothesis subtype)

Actors represent **identity hypotheses**, not resolved entities.

**Fields**
- `actor_id`
- `labels` (names, aliases, spellings)
- `evidence_spans` (TextSpan)
- `confidence`

Actors may be merged or split later; history is preserved.

---

### Event (Hypothesis subtype)

Represents a hypothesized occurrence.

**Fields**
- `event_id`
- `description`
- `time_bounds` (optional)
- `evidence_spans` (TextSpan)
- `confidence`

---

### Relationship

Directed relationships between ITIR objects.

**Types**
- `supports`
- `contradicts`
- `implies`
- `associated_with`
- `uncertain`

**Required**
- `source_id`
- `target_id`
- `relation_type`
- `provenance_spans` (TextSpan)
- `confidence`

---

## Redactions & Uncertainty

Redactions are **structural spans in SL**.

In ITIR:
- redactions may anchor hypotheses
- uncertainty must be explicit
- no filling or guessing allowed

Example:
> "Actor A appears adjacent to repeated redactions in documents X, Y."

---

## Branching & Attribution

All ITIR objects belong to a **branch**.

Branches:
- may diverge
- may be merged
- never overwrite history

Each object records:
- creator
- branch
- timestamp

---

## Invariants

- No ITIR object without TextSpan provenance
- No silent merges
- No inferred truth
- No mutation of SL text
- Deterministic references
- Context is mandatory: every artifact view includes temporal and epistemic
  frame metadata (date/time, venue/medium, known public facts at the time)

## Context Anchoring (Suite-Level Requirement)

ITIR preserves interpretive integrity by enforcing knowledge-state overlays:
- What was publicly known at the time
- What legal status existed at the time
- What was later revealed (and must be visually separated)

---

## Non-goals

ITIR does NOT:
- decide truth
- rank narratives
- resolve guilt
- enforce consensus
- overwrite sources

---

## Summary

ITIR enables **explicit, auditable disagreement** over a shared factual
substrate.

SL guarantees everyone sees the same text.
ITIR allows them to argue responsibly.
