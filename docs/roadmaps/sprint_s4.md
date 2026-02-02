# Sprint S4 — Normative Semantics Layer (Logic-Tree Native)

Goal: sound, deterministic, non-inventive semantic layer that extracts normative meaning (obligations, permissions, prohibitions, exclusions) from statutes. Strictly additive: no changes to LT-REF-1..6, CR-ID, DIFF, or provenance semantics.

## Scope overview

| Sub-Sprint | Capability                           | Status |
| ---------- | ------------------------------------ | ------ |
| S4.1       | Obligation detection (clause-scoped) | ✅ done |
| S4.2       | Condition & exception structure      | ⏳ next |
| S4.3       | Obligation identity & diff           | ⏳      |
| S4.4       | Obligation graph & compliance hooks  | ⏳      |
| S4.5       | Case-law bridge (optional/preview)   | ⏳      |

Hard constraint: No changes to extraction, references, CR-ID/DIFF/PROV, or LT-REF invariants.

## S4.1 — Obligation detection (complete)
- Established that clause-scoped logic tree + modal triggers yields obligation atoms.
- CR-ID binding only; no regex soup; deterministic and OCR-stable.

## S4.2 — Conditions, exceptions, scope narrowing (next)
Why: obligations are currently flat; law is conditional.

Deliverables:
- `ConditionAtom`: type ∈ {if, unless, except, subject_to}, span, clause_id.
- Enrich `ObligationAtom.conditions` with ConditionAtoms (not free text).

Invariants:
- COND-1: Conditions are clause-local (same span containment as OBL-1 analogue).
- COND-2: Removing conditions does not change obligation identity (future S4.3).
- COND-3: OCR/spacing noise does not change condition attachment.
- COND-4: No cross-clause leakage.

Tests:
- Detect `if / unless / except / subject to` within clause spans.
- Exceptions do not create new obligations.
- Clause boundary isolation.

Stop condition: can represent “must do X unless Y / subject to s 12” without inventing or flattening semantics.

## S4.3 — Obligation identity & diff
Goal: obligations become diffable and comparable like references.

Deliverables:
- `ObligationIdentity` (CR-OBL) derived from:
  - obligation type
  - modality (canonical surface)
  - set of bound reference identity hashes
  - condition structure (types ordered deterministically)
  - clause role (position index, not raw clause_id text)
- `ObligationDiff`: added / removed / unchanged (identity-hash based).

Invariants:
- OBL-ID-1: Pure function of normalized obligation data; no source text dependency beyond tokens.
- OBL-ID-2: Stable under OCR/spacing noise.
- OBL-ID-3: Reordering/renumbering clauses without semantic change → no diff.
- OBL-ID-4: Identity never feeds back into extraction.

Tests:
- OCR noise → no diff.
- Clause renumbering → no diff.
- Amendment introducing one new duty → exactly one added.

## S4.4 — Obligation graph & compliance hooks
Deliverables:
- `ObligationGraph`: nodes = ObligationIdentity; edges = conditional_on / exception_to / depends_on.
- Minimal compliance hooks:
  - `obligations_for(reference_identity)`
  - `obligations_triggered_by(facts)` (stub, deterministic)

Invariants:
- No cross-document edges.
- Deterministic construction; acyclic unless statute self-references explicitly.

## S4.5 — Case-law bridge (preview/optional)
Purpose: show obligations can be interpreted in holdings later.
- Map holding language (“required to…”, “no obligation arose…”) to obligation reinforcement/negation behind a feature flag.

## Done criteria for S4
1) Extract obligations from a statute.
2) Bind them to references via CR-ID.
3) Diff them across versions.
4) Traverse them as a graph.
5) Achieve all of the above without touching extraction/reference invariants.

## Recommended order
1) Implement S4.2 (conditions & exceptions).
2) Implement S4.3 (obligation identity & diff).
3) Implement S4.4 (graph + hooks).
4) Optionally prototype S4.5 behind a flag.
