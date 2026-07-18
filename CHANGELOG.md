# 2026-07-18

- Add the capability-oriented PostgreSQL compiler runtime under `corpus`,
  `language`, `algebra`, `pnf`, `evidence`, `resolution`, `execution`, and
  `governance` schemas. The generic compiler schema contains no legal-,
  Wikidata-, WorldMonitor-, GWB-, or AU-specific table families.
- Make PostgreSQL the default directory-compilation persistence path. The CLI
  now requires `DATABASE_URL`/`--database-url`; filesystem semantic JSON is an
  explicit `--emit-legacy-json` compatibility export only.
- Add a 4-byte logical lexeme dictionary plus frequency-ranked corpus-local
  symbols, unsigned-varint token streams, delta-coded offsets, posting-block
  storage, and a benchmark harness. Sparse token rows remain optional query
  projections rather than the dense canonical representation.
- Add direct transactional persistence for source/canonical content, document
  occurrences, spans, annotations, factors, PNF graphs, local evidence,
  demands, typed meets, refinements, and failure receipts. Add generic external
  snapshot/assertion persistence without registry-specific tables.
- Add PostgreSQL views for PNF inspection, document summaries, unresolved
  demands, review queues, and dependency staleness. Add an immutable migration
  filename/hash ledger.
- Add the generic local-only directory compilation kernel. `compile_document`
  now supplies one shared per-document semantic operation, while
  `compile_directory` only inventories bounded media, invokes that operation,
  writes append-only content-addressed projections, and groups unresolved
  demands. The initial UTF-8 text capability performs no network work,
  external identity selection, readiness promotion, or cross-document identity
  closure; failures and unsupported media remain explicit manifest receipts.
- Expose the same generic directory kernel through
  `scripts/compile_corpus.py` and the public `sensiblaw` package, with a
  declarative `CompilerContext` rather than corpus/profile selectors. Add a
  compact GWB proof corpus fixture solely for deterministic regression,
  including duplicate-occurrence, resume, unsupported-media, and failure-
  isolation coverage.

# 2026-07-17

- Implement P0c.5's registry-neutral evidence-control-plane carrier. Immutable
  cache metadata, typed backend capabilities, explicit cache/unavailable/
  budget outcomes, and deterministic rate-limit-aware microbatch plans now sit
  after semantic demand equivalence. This is plan-only: it performs no I/O,
  selects no identity, reconciles no event, and mutates no PNF.

- Implement P0c.3/P0c.4 typed resolution subjects and semantic demand-
  equivalence receipts before scheduler work. Entity/event/property/local-
  cluster subjects and formal event roles remain distinct; equivalent demands
  retain every member and are only marked coalescible, with no backend, cache,
  retrieval, resolution, PNF, or promotion effect.
- Implement P0c.2's generic backend-free ResolutionDemand projection. Only
  unresolved closure obligations now produce source-anchored, facet-specific,
  budget-labelled evidence plans; no backend selection, request, resolution,
  or PNF mutation occurs.
- Implement P0c.1's generic factorized PartialPNF carrier and independent
  closure-pressure receipt. Document-bounded slots now retain compatible local
  type alternatives without combining them, making a registry request,
  resolving identity, or asserting a claim.
- Implement P0b.8's generic candidate-only local typing and coverage-pressure
  carrier. Form and parser evidence can now produce explicit local semantic
  alternatives and per-mention coverage states without selecting identity,
  constructing PNF, contacting a registry, or promoting a fact.
- Correct P0b.7 form composition so every compatible declared component path
  is emitted; input and serialization order can no longer suppress a form
  alternative.
- Implement P0b.7's generic candidate-only form derivation carrier. Anchored
  source forms now produce explicit surface, token, numeric, abbreviation, and
  profile-derived alternatives plus declared form relations, before entity
  retrieval or PNF interpretation. Deterministic encoding order is explicitly
  non-semantic; no alias truth, event identity, metonymy, resolution, or
  promotion is introduced.
