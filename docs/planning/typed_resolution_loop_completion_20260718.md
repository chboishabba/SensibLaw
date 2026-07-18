# Typed Resolution Loop Completion

Date: 2026-07-18
Status: implemented review branch

This tranche completes the semantic back half after the registry-neutral P0c.5 scheduler.

## Implemented

- deterministic document-local evidence projection;
- revision-pinned Wikidata snapshot adaptation;
- WorldMonitor snapshot adaptation preserving occurrence, observation, cluster, forecast, report, alert, and rolling-state roles;
- coordinate-wise entity and event reconciliation without scalar-only identity closure;
- factor-local PartialPNF refinement receipts;
- review-only readiness outcomes: `promote | hold | abstain | audit`;
- compact GWB and AU end-to-end proof fixtures;
- minimal append-only SQLite artifact storage.

## Authority boundaries

Evidence snapshots do not select identities. Reconciliation assessments do not promote claims. PNF refinement changes only the named factor and emits an unchanged-factor witness. Readiness promotion means review eligibility only and carries no editing authority.

## Event compatibility

Event reconciliation retains independent coordinates for:

- temporal relation;
- spatial relation;
- participant-role relation;
- event-type relation;
- linguistic form relation;
- source lineage;
- observation-to-occurrence role.

WorldMonitor records are never coerced into occurrences. An observation, cluster, forecast, report, alert, or rolling state remains that formal artifact unless a later typed relation connects it to an occurrence.

## Proof outcomes

The AU fixture closes a court identity through shared entity/type/form obligations and reaches review promotion. The GWB fixture resolves the person identity but remains held on the event factor because event lineage or occurrence evidence is not fully closed. This difference is intentional: the proof demonstrates that the readiness oracle preserves a real unresolved residual rather than forcing a successful result.

## Operational boundary

The append-only SQLite store is intentionally minimal. It persists immutable demand/evidence/assessment/refinement artifacts without freezing a universal graph schema. Live network calls, production endpoint discovery, asynchronous workers, large-corpus columnar projections, and broad replay remain deployment work above the now-proven semantic interfaces.
