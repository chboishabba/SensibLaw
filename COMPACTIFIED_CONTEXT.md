# COMPACTIFIED_CONTEXT

## Purpose
Snapshot of intent while applying the get-shit-done and update-docs-todo-implement workflows before touching code.

## Objective
Document near-term targets from `todo.md`; implementation and tests remain paused until TODOs reflect this intent.

## Near-term intent (from todo.md)
- Graphviz proof trees: define DOT schema and rendering targets aligned with README Graphviz prerequisites.
- NetworkX traversal: shape public traversal API and core queries; keep analysis layer separate per `docs/ITIR.md`.
- SQLite + FTS5 storage: outline schema, migrations, and index plan; tie to `docs/versioning.md` and `docs/roadmap.md`.
- pdfminer.six parsing: sketch extraction pipeline and fixtures, reusing README ingestion constraints.
- FastAPI service: list endpoints and response models; reconcile with `src/api` sample routes.
- Requests ingestion: capture external source catalog plus rate-limit/backoff policy per `docs/external_ingestion.md`.
- Streamline viz: confirm Canvas 2D/Regl/WebGL/Svelte+TS approach referencing `TIMELINE_STREAM_VIZ_ROADMAP.md` and `STREAMLINE_FEATURE_PROPOSAL.md`.
- NLP/ontology pipeline: follow Sprint 1–4 stack (spaCy adapter hardening, logic_tree integration, ontology binding, API/UX surface) consistent with README “NLP Integration Snapshot,” `docs/nlp_pipelines.md`, and `docs/roadmap.md`.

## Proposed priority order (highest → lowest)
1) SQLite + FTS5 storage and migrations (unblocks traversal, API, and search).  
2) pdfminer.six ingestion pipeline + fixtures (feeds storage).  
3) NLP/ontology pipeline Sprint 1–2 (spaCy adapter + logic_tree wiring) to unlock enriched graph exports.  
4) NetworkX traversal API/core queries (depends on storage + NLP outputs).  
5) Graphviz proof tree DOT schema and rendering targets (consumes traversal + NLP labels).  
6) FastAPI endpoints + response models (surface traversal/search; depend on storage).  
7) Requests-based external ingestion catalog + rate-limit/backoff policy.  
8) Streamline viz (Canvas/Regl/WebGL/Svelte) atop API data once prior layers are stable.

## Next milestone scope (proposed)
- Deliver ingestion-to-query foundation: PDF → parsed artifacts → SQLite/FTS store → traversal API → Graphviz DOT render.  
- Include NLP Sprint 1–2 (deterministic spaCy adapter, token coverage, logic_tree integration hooks).  
- Exclude full ontology binding, external ingestion, and Streamline UI from this milestone; stage them next.

## Dependencies / infra constraints
- Graphviz CLI (`dot`) must be installed per README prerequisites.  
- spaCy model downloads (e.g., `en_core_web_sm`) require network; cache models locally or vendor wheels.  
- FTS5 availability confirmed in SQLite build; migrations need to guard for missing extension.  
- Test PDFs/fixtures required for pdfminer; store under `tests/fixtures/`.  
- API and traversal layers assume stable schema versioning (`docs/versioning.md`).

## Assumptions
- Python 3.11 target with 3.10 fallback; format with Ruff.
- No implementation yet; TODO updates follow this intent.

## Open questions
- Confirm acceptance of the proposed priority order and milestone scope.  
- Any compliance constraints for storing PDFs / scraped sources?  
- Which spaCy model size is acceptable for production footprints?
