# Sprint S7 — Interfaces, Activation, Cross-Document Topology (Non-Reasoning)

Goal: expose, exercise, and extend the S6 normative surfaces **without inference or judgment** by (C) validating them through human-visible interfaces, (A) adding fact-driven activation metadata, and (B) projecting explicit cross-document relationships once the earlier tracks are stable.

## Entry criteria
- S6 read-only surfaces (query, explanation, alignment, projections, schemas) are green and identity-stable.
- No pending reasoning/ontology features; OBL-ID/DIFF and CR-ID invariants frozen.

## Scope and guardrails
- In scope: read-only UI/API/CLI exposure, fact-driven activation status, explicit cross-document edges with textual basis.
- Out of scope: compliance judgments, inferred facts, ontology/semantic expansion, precedence/conflict resolution, identity mutation.
- All new outputs versioned; feature-flag anything that could destabilize existing payloads.

## Track plan and sequencing
| Track | Capability | Status | Sequencing logic |
| ----- | ---------- | ------ | ---------------- |
| **C** | Human Interfaces (API/CLI/Streamlit read-only views) | 🔜 planned | Runs first; zero semantic risk; validates payload determinism. |
| **A** | Compliance Simulation (fact-driven activation metadata) | ⏳ planned | Starts after C confirms lifecycle correctness. |
| **B** | Cross-Document Norm Topology (explicit edge graph) | ⏳ planned | Starts after A stabilizes activation semantics; highest coupling. |

## Deliverables by track
### S7-C — Human Interfaces (read-only)
- API endpoints: `/obligations/query`, `/obligations/explain`, `/obligations/alignment`, `/obligations/projections/{actor|action|clause|timeline}`.
- Streamlit UI: actor/action filters, clause drill-down (explanation), alignment diff viewer.
- CLI: `--emit-projections`, `--emit-explanation` (alignment already via `--emit-obligation-alignment`).
- Tests: deterministic JSON snapshots per endpoint; UI smoke (sample corpus renders, schema-valid); CLI golden outputs.
- Guardrails: no new atoms, no activation logic, no cross-document joins; outputs byte-for-byte schema-stable.

### S7-A — Compliance Simulation (descriptive activation only)
- Inputs: `FactEnvelope` `{ key, value, time }` (no defaults).
- Function: `simulate_activation(obligations, facts, t)` returning `ActivationResult` (active / inactive / terminated + reasons).
- CLI/API (exposed, gated): `--simulate-activation <facts.json>` and `POST /obligations/activate`.
- Tests: activation only when explicit trigger text matches facts; missing facts keep obligations inactive; identity unchanged; no compliance labels.
- Guardrails: no inferred facts, no compliance judgments, activation is orthogonal metadata.

### S7-B — Cross-Document Norm Topology (explicit edges)
- Graph payload `obligation.crossdoc.v1`: nodes = OBL-ID; edges require textual citation; types = `supersedes | subject_to | exception_chain | temporal_override`.
- Time overlays only with explicit dates; cycles flagged not resolved.
- Tests: no edge without citation; renumbering/OCR noise invariant; cycles reported not pruned; no conflict resolution.
- Guardrails: no inferred edges, no precedence reasoning, no “effective law” computation.

## Red-flag tests (must fail on reasoning creep)
- Identity freeze: S7 surfaces never change OBL-ID/DIFF.
- Interfaces passive: queries/views cannot add/remove obligations; deterministic ordering enforced.
- Activation discipline: no trigger text → never active; missing facts → inactive; no compliance labels; activation cannot mutate identity.
- Cross-doc discipline: every edge requires citation spans; formatting changes do not alter edges; cycles flagged, not fixed.

## Exit criteria
- C, A, B delivered with versioned schemas and feature flags where needed.
- Red-flag tests in CI guard against reasoning, inference, or identity drift.
- UI + CLI + API expose exactly what the system already knows; no ontology expansion or semantic normalization.

## Delivery rules
- Tests-first per track; keep new surfaces flag-gated until deterministic.
- Deterministic JSON ordering for all payloads to preserve diffability and snapshots.
- No cross-track identity changes; activation metadata and cross-doc edges remain additive and orthogonal.

## TODO (implementation-ready checklist)
- Add FastAPI routes for `/obligations/query`, `/obligations/explain`, `/obligations/alignment`, `/obligations/projections/{view}` using S6 primitives; deterministic JSON + schema versions.
- Extend CLI (`sensiblaw obligations`) to emit projections (`--emit-projections`) and explanations (`--emit-explanation`); reuse existing alignment flag for diffs.
- Wire snapshot/golden tests for API + CLI outputs (fixtures from sample corpus) as red flags.
- Keep all new outputs flag-gated and identity-neutral; no activation or cross-doc logic until tracks A/B start.
- Track A prep: FactEnvelope doc and activation red-flag tests in place; activation simulation is descriptive only and identity-neutral.
