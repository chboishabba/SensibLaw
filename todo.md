# TODO

- Milestone (current): ingestion-to-query foundation — PDF → parsed artifacts → SQLite/FTS → traversal API → Graphviz DOT render; include NLP Sprints 1–2 hooks into logic_tree; defer ontology binding, external ingestion, and Streamline UI to next milestone.
- Sprint (active): deterministic logic tree spine — ship `logic-tree-v1` IR per docs/logic_tree_ir.md (purely structural, deterministic, round-trip safe, DOT-exportable).
- Priority order (highest → lowest):
  1) SQLite + FTS5 → storage and full-text search (schema, migrations, index plan; tie to docs/versioning.md + docs/roadmap.md)
  2) pdfminer.six → PDF parsing (extraction pipeline + fixtures; reuse README ingestion constraints)
  3) NLP → Sprint 1–2 (spaCy adapter hardening, deterministic token offsets/POS/lemma/dep coverage, matcher callbacks set token._.class_, pipeline/__init__.py consumes tokens; regression fixtures in tests/nlp)
  4) NetworkX → graph traversal (public traversal API + core queries; keep analysis layer separate per docs/ITIR.md)
  5) Graphviz → proof tree rendering (define DOT schema + rendering targets; align with README Graphviz prerequisites; consume traversal/NLP labels)
  6) FastAPI → API service (endpoint list + response models; reconcile with src/api sample routes; surface traversal/search)
  7) Requests → external data retrieval (source catalog + rate-limit/backoff policy; match docs/external_ingestion.md patterns)
  8) Streamline (Canvas 2D + Regl/WebGL, Svelte/TypeScript front end as needed) → visualisation (see TIMELINE_STREAM_VIZ_ROADMAP.md and STREAMLINE_FEATURE_PROPOSAL.md)
- Logic tree sprint TODOs (tracked this week):
  - Implement `logic-tree-v1` builder: deterministic IDs, clause segmentation, node typing, spans, edge typing (SEQUENCE/DEPENDS_ON/QUALIFIES/EXCEPTS), empty-input handling.
  - Traversal helpers: preorder, postorder, root-to-leaf paths with stable ordering.
  - Persistence helpers: `to_dict`, `from_dict`, JSON round-trip fidelity; version/tag set to `logic-tree-v1`.
  - DOT export: deterministic ordering, node labels by node_type/text, optional color map by node_type.
  - Tests: empty input, single clause, multi-clause sequence, qualifiers/exceptions, determinism (build twice/diff), DOT snapshot.
  - Example artifact: checked-in DOT sample for a small clause.
  - Inline ordering docstrings + SQLite projection helper with `ord` to preserve traversal order in storage (SQLite as projection, not authority).
- Dependencies/infra to log and resolve:
  - Graphviz CLI (`dot`) available per README.
  - spaCy model downloads/cache strategy (e.g., en_core_web_sm); network needed once.
  - FTS5 availability in SQLite build; migrations must gate on extension.
  - PDF fixtures stored under tests/fixtures/ for pdfminer regression.
  - Stable schema versioning contract per docs/versioning.md for API/traversal consumers.
- NLP → ontology pipeline alignment (full stack for later milestone)
  - Sprint 3: ontology binding (RuleAtom → LegalSystem/WrongType/ProtectedInterest/ValueFrame tables, migrations + DAO/hooks, graph export reflects new links)
  - Sprint 4: API/UX surface (FastAPI routes and Streamlit/CLI expose enriched RuleAtom/ontology joins; provenance receipts stored; end-to-end regression)
