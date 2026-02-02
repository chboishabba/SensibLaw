# Sprint S6 — Normative Reasoning Surfaces (Non-Judgmental)

Goal: expose queryable, explainable, composable views over the S4–S5 normative lattice **without adding legal reasoning, compliance judgement, ontology lookup, or ML**. S6 is a usability layer on top of a frozen, text-derived structure.

## Entry criteria (all satisfied)
- Obligations are clause-local with actor/action/object binding, scopes, lifecycle, and deterministic graph projection.
- Identity/diff surfaces (CR-ID, OBL-ID) are stable and flag-gated for actor/action.
- Stability/drift guards are green; formatting/OCR noise does not alter identities.

## Scope and guardrails
- In scope: read-only queries, explanations, diff alignment, deterministic view projections, and versioned schemas for downstream consumers.
- Out of scope: compliance checking, legal reasoning/defeasibility, ontologies/taxonomies, ML or probabilistic inference, cross-document norm resolution.
- Constraint: S5 invariants remain frozen—clause-local, text-derived only; no invented edges or spans.

## Sub-sprints and status
| Sub-sprint | Capability | Status |
| ---------- | ---------- | ------ |
| S6.1 | Obligation Query API (read-only filters by actor/action/object/scope/lifecycle; flag-respecting) | ✅ done |
| S6.2 | Explanation & trace surfaces (deterministic payloads mapping atoms → source spans) | ✅ done |
| S6.3 | Cross-version obligation alignment (alignment report with metadata deltas) | ✅ done |
| S6.4 | Normative view projections (actor/action/timeline/clause views; deterministic outputs) | ✅ done |
| S6.5 | External consumer contracts (versioned JSON schemas for obligation/explanation/diff/graph) | 🚧 started (query/explanation/alignment v1 seeded) |
| S6.6 | Hard stop & gate review (no-reasoning guard doc + red-flag tests) | ✅ done |

## Acceptance criteria
- Query helpers return deterministic sets unaffected by formatting/OCR noise; actor/action flags respected.
- Explanations round-trip to clause IDs and text spans; stable under renumbering/whitespace changes.
- Alignment reports differentiate unchanged/modified/added/removed; scope/lifecycle changes appear as metadata deltas.
- View projections produce reproducible outputs and never invent nodes/edges.
- Published schemas versioned; backward-compatible parsing for prior payloads.
- Red-flag tests fail if any reasoning/compliance/ontology behavior slips in.

## Recommended sequencing
1) S6.1 Obligation Query API (complete)
2) S6.2 Explanation surfaces (complete)
3) S6.3 Cross-version alignment (complete)
4) S6.4 View projections (complete)
5) S6.5 External contracts (schemas) — stubs added (query, explanation, alignment), finalize after S6.3 completion
6) S6.6 Gate review and no-reasoning guards (complete)

## Delivery rules
- Tests first for each sub-sprint; keep new surfaces feature-flagged if risk exists.
- Outputs are read-only and identity-neutral—no mutation of obligation records.
- Deterministic ordering for all emitted lists to preserve diffability.

## Implementation notes (S6.1–S6.6)
- Query API provides deterministic filters over actor/action/object/scope/lifecycle/clause/ref/modality, preserving input order and respecting actor/action binding flags.
- Explanation payloads emit clause-local atom details (text + normalized + spans) with content-relative spans that survive numbering/formatting noise; ordering of scopes/lifecycle is deterministic.
- Alignment payload emits added/removed/unchanged and structured change lists; schema `obligation.alignment.v1` seeded.
- No-reasoning guard doc added (`docs/no_reasoning_contract.md`) plus red-flag tests ensuring: modal required, no inferred edges, identity ignores scopes/lifecycle, alignment only when deltas exist, schema versions frozen.
- Schema stubs seeded:
  - `obligation.query.v1`
  - `obligation.explanation.v1`
  - `obligation.alignment.v1`
  Final schema versions will be frozen in S6.5; bump versions on any field changes.
