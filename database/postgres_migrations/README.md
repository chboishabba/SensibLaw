# Postgres Migrations

- Location for the Postgres schema migrations; run in lexical order.
- Apply with `scripts/apply_pg_migrations.sh` (honours `PG*` env vars or `DATABASE_URL`).
- PostgreSQL is the sole active semantic persistence spine. SQLite is retained
  only for bounded legacy import/replay fixtures and must not become a runtime
  semantic authority.
- JSON is a detached presentation format. It may be emitted by projections but
  is never re-ingested as a graph, world-model, or follow-workflow input.
- Supersedes the ad-hoc SQL under `migrations/` and `schemas/migrations/`, which are kept only for reference.
- `007_compiler_substrate.sql` is the additive generic compiler runtime. It
  stores immutable declarations, documents, builds/dependencies, shared
  annotations, factorised PNF structure, typed meets, factor revisions, and
  unresolved demands without requiring a legal-ontology row.
- `024_generic_follow_projection.sql` persists derived-only, challengeable
  follow projections as rows with FK closure and exposes legal/non-legal views.
- `086_consumer_indexed_reopenable_runtime.sql` adds the durable F/P/Q/R/O
  execution carrier, signed cumulative evidence, explicit open-world relevance,
  exact parser->argument support transport, identity/factor audits, and runtime
  measurement surfaces without replacing the set-based demand planner.
- `087_reopenable_runtime_hardening.sql` makes runtime history append-only by
  corrective event and permits durable Q->P reopening independently of the
  latest ephemeral planner row. It preserves the original v1 view column order
  before appending diagnostics so upgrades are safe under PostgreSQL
  `CREATE OR REPLACE VIEW` rules.
- `088_progressive_reopenable_resolution.sql` adds cumulative H3/H6/H9
  preference/escalation surfaces. Preference is explicitly non-proof and never
  writes `semantic_pnf_frontier_resolution` or identity witnesses.
- `089_numeric_incremental_runtime_economy.sql` makes the ordinary post-parser
  path numeric and sparse: hot symbol ids, bounded parser ancestry, rebuildable
  current-state projections, lazy horizon work, reverse dependencies, frequency
  codebooks, contextual world candidate fibres, and corpus reuse measurements.
- `090_numeric_parser_evidence_and_learning.sql` compiles parser identity cues to
  numeric evidence and adds controlled ancestry/cache helpers without granting
  lexical or parser evidence identity authority.
- `091_numeric_incremental_wiring.sql` wires H3 seeding, evidence wakeups,
  entity-label maintenance, numeric Wikidata candidate caching, and empirical
  reuse recording onto the existing carrier.
- `092_consumer_sufficient_context_and_tape.sql` adds typed candidate context
  requirements, signed mention-local context observations, exact hot/cold
  extensional verification, consumer sufficiency receipts, controlled-workload
  identity fields, and a rebuildable packed numeric parser-tape cache.
- `093_controlled_learning_and_tape_wiring.sql` provides the controlled reuse
  recorder and two-phase tape registration. Supplying packed bytes never
  self-certifies exactness; Python must independently decode and compare them
  against canonical parser observations before marking the cache verified.
- `094_context_scope_and_consumer_horizon_queue.sql` is the effective
  consumer-execution implementation: it scopes world-context comparison by the
  mention's numeric label, replaces the first 092 consumer advance function
  with an independent `(consumer, query, policy)` horizon queue, and adds sparse
  consumer-indexed reverse dependencies. A consumer's safe early stop therefore
  cannot suppress global proof-required work or another consumer's deeper work.
- `095_context_ties_and_sufficiency_revision.sql` preserves ambiguity and
  revision: only a unique top positively witnessed context candidate may be
  automatically attached; ties remain unresolved. Sufficiency receipts are
  append-only/revisioned and may be withdrawn, with query factorisation accepted
  only for query-only consumers and policy/full-future certificates required
  once a policy may act. It also adds demand FKs to hot current projections for
  new/changed rows.
- See `docs/reopenable_runtime_architecture.md`,
  `docs/numeric_incremental_runtime_economy.md`, and
  `scripts/audit_reopenable_runtime_migrations.py` for architecture and
  source-dependency audit context.

## Migration identifier guardrail

The directory currently contains duplicate `006_*` and `007_*` prefixes.
Filename plus content hash remains the applied-migration identity, so an
already-applied file must not be renamed in place. Until a
checksum-preserving renumbering plan is complete:

- every new migration must use a previously unused numeric prefix;
- reviewers must inspect full filenames rather than treating the prefix as a
  unique identifier;
- no migration may be copied into the deprecated SQLite or superseded
  reference tracks.
