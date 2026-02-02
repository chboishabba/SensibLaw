# Sprint S5 — Normative Structure & Reach

Goal: turn extracted obligations into a **structured, navigable normative system** (actors, actions/objects, scopes, lifecycle, interactions) without adding interpretation or ML. Strictly additive to S4; all LT-REF, CR-ID/DIFF, OBL-ID/DIFF, and provenance invariants remain frozen.

## Scope overview

| Sub-Sprint | Capability                               | Status |
| ---------- | ---------------------------------------- | ------ |
| S5.1       | Actor & role binding (who is bound)      | ✅ done |
| S5.2       | Action & object decomposition (what)     | ✅ done |
| S5.3       | Scope & reach (where/when)               | ✅ done |
| S5.4       | Obligation lifecycle (activation/stop)   | ✅ done |
| S5.5       | Normative interaction graph (edges)      | ✅ done (deterministic projection) |
| S5.6       | Stability & drift guard hardening        | ✅ done |

## Out of scope for S5 (guardrails)

- Compliance engines, legal reasoning, or judgement calls
- ML/ontologies/case-law interpretation
- Fact pattern evaluation or Q&A
- Cross-clause inference beyond explicit text

## Hard constraints

- No changes to extraction, reference, or obligation identity/diff invariants.
- Text-derived only; no ontology or external registry lookups.
- Clause-local attachment; no invented actors/scopes/lifecycle triggers.
- Outputs are deterministic and OCR/whitespace stable.

## S5.1 — Actor & Role Binding (Who is bound) — ✅ complete

Deliverables
- `ActorAtom` extracted from clause-local phrases (e.g., “a person”, “the operator”, “the Minister”, “a public authority”).
- Attach `ActorAtom` to `ObligationAtom` without changing obligation existence.

Invariants
- ACT-1: Clause-local extraction only.
- ACT-2: No inference across clauses.
- ACT-3: No ontology lookup or synonym expansion.
- ACT-4: Identity is text-derived spans only; OCR noise should normalize.

Tests (implemented)
- Same obligation text with different actor → distinct obligation identities.
- OCR/whitespace noise → same actor identity.
- Missing actor → obligation still exists (actor = unknown).
- Flag off (`OBLIGATIONS_ENABLE_ACTOR_BINDING` or `--disable-actor-binding`) → actor omitted, identities ignore actor.
- Fixtures: distinct actors, missing actor, OCR noise, conjunction, titled actor.

Status: shipped (code, tests, CLI flag).

## S5.2 — Action & Object Decomposition (What is required/prohibited) — ✅ complete

Deliverables
- `ActionAtom` (normalized verb head/phrase) and `ObjectAtom` (acted-upon phrase) extracted clause-locally; feature-flagged via `OBLIGATIONS_ENABLE_ACTION_BINDING` / CLI `--disable-action-binding`.
- Obligations carry action/object; identity hashing incorporates them when flag enabled.

Status
- Implemented with tests: distinct actions diff; spacing/OCR noise stable; missing object allowed; numbering/formatting stable.

## S5.3 — Scope & Reach (Where / When) — ✅ complete

Deliverables
- `ScopeAtom` (time/place/context) captured from explicit phrases; attachments only, identity-neutral.

Status
- Implemented with tests: time (“within 7 days”), place (“on the premises”), context (“during operations”); identities unchanged by scopes.

## S5.4 — Obligation Lifecycle (Activation & Termination) — ✅ complete

Deliverables
- Lifecycle triggers (activation/termination) captured from explicit cues (on/when/upon/while vs until/ceases).

Status
- Implemented with tests; lifecycle metadata does not alter identity.

## S5.5 — Normative Interaction Graph — ✅ complete

Deliverables
- Deterministic graph projection: nodes = obligation identities; edges from explicit condition/exception markers.

Status
- Implemented with tests; no inferred edges; deterministic projection.

## S5.6 — Stability & Drift Guard Suite — ✅ complete

Deliverables
- Snapshot-style tests for numbering/formatting/OCR noise and clause reordering; flag toggling for actor/action identity components.

Status
- Implemented; identities stable under formatting noise, deterministic diff behavior; flags toggle identity orthogonally.

## Acceptance criteria for Sprint S5
- Obligations carry actor, action/object, scope, and lifecycle metadata without violating existing identities/diffs.
- Clause-local, text-derived, deterministic extraction across all new atoms.
- Normative interaction graph emitted with new edge types and stable hashing.
- Full regression suite stays green; new tests added for each sub-sprint invariants.

## Recommended sequencing
1) S5.1 actors/roles (unblocks lifecycle scoping and graph edges).
2) S5.2 actions/objects (completes obligation payload structure).
3) S5.3 scopes (activation context).
4) S5.4 lifecycle (activation/termination semantics).
5) S5.5 graph edges (wire new atoms into navigation).

## Delivery rules
- Tests first for each sub-sprint; keep feature-flagged if needed.
- No ML/ontologies; stay deterministic and text-grounded.
- Additive only; avoid regressions to S4 semantics and invariants.
