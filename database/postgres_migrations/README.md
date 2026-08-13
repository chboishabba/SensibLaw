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
- `089_numeric_incremental_runtime_economy.sql` adds the numeric hot path,
  bounded dependency ancestry, sparse structural-support observatory, rebuildable
  hot current-state projections, lazy H3/H6/H9 queues, reverse dependencies,
  frequency-adaptive codebooks and the contextual world-candidate cache.
- `090_numeric_parser_evidence_and_learning.sql` adds numeric parser-derived
  evidence and initial corpus-learning surfaces.
- `090a_demand_structural_source_anchor.sql` supplies the proof-neutral demand
  `source_object_id` consumed by 091 only when existing source-region + lexical
  coordinates identify exactly one object; ambiguous demands remain unanchored.
- `091_numeric_incremental_wiring.sql` wires demand/evidence wakeups, incremental
  entity-label caching, numeric Wikidata candidate boundaries and corpus-reuse
  measurements.
- `092_consumer_sufficient_context_and_tape.sql` through
  `095_context_ties_and_sufficiency_revision.sql` add exact hot-state equality,
  typed contextual requirements, isolated consumer/query/policy horizon queues,
  controlled workload identity, provenance-complete packed parser tape,
  tie-preserving contextual choice, and revisioned/withdrawable sufficiency.
- `096_late_external_demand_planner.sql` adds explicit consumer H9 external
  needs, deduplicated physical requests with many semantic members, local cache
  probes and bounded provider leases. Proper nouns do not implicitly cause
  provider requests.
- `097_external_evidence_projection_and_wakeup.sql` persists provider evidence
  and wakes only affected consumer H9 fibres; eligible symbol-valued facts may
  become contextual requirements but never identity proofs.
- `098_external_demand_hardening_and_receipts.sql` makes property-axis need
  identity exact, re-probes expired leases before retry, preserves external
  evidence immutably, and records literal provider batching receipts.
- `099_external_fact_axis_reuse.sql` separates provider facts from the first
  consumer's axis interpretation so cached facts can be re-projected for later
  consumers without another provider call.
- `100_external_provider_boundary_projection.sql` keeps PostgreSQL-local
  surrogates inside the database: provider workers receive label text and
  provider-native entity/property numeric ids only.
- `101_literal_provider_call_receipts.sql` ensures provider call counts remain
  literal network/provider I/O; local validation failures may consume zero calls.
- `102_external_identity_blocked_state.sql` makes unsupported proof-producing
  identity alignment a durable blocked state rather than a retry loop.
- `103_external_source_freshness_and_snapshot_provenance.sql` makes source age
  consumer-relative: candidate/property cache rows carry source epochs and a
  shared external request adopts the strongest freshness floor among its member
  fibres. Tightening an existing need reopens only the affected physical request.
- `104_external_freshness_lease_projection.sql` carries that freshness floor to
  provider workers while preserving the migration-100 boundary: labels leave as
  text and entities/properties leave as provider-native numeric identifiers,
  never database-local surrogates.
- `105_monotone_external_candidate_fibres.sql` makes label->world candidate
  discovery monotone. Partial or empty provider reads cannot erase older
  candidates; newer known-age observations may refresh rank/provenance.
- `106_external_freshness_exact_member_floor.sql` recomputes a shared physical
  request's freshness floor from its currently active semantic members, allowing
  the floor to relax again when stronger consumers withdraw.
- `107_external_freshness_lease_race_guard.sql` prevents a worker leased under an
  older freshness floor from completing a request after that floor tightens.
- `108_external_evidence_completion_separation.sql` separates immutable cold
  evidence persistence from lease-aware request completion and H9 wakeup.
- `109_current_external_context_projection.sql` makes external contextual
  requirements a rebuildable hot projection of immutable evidence, selecting
  only the newest admissible source epoch while retaining all cold history.
- `110_residual_driven_h6_and_zero_need_h9.sql` adds the first real H6
  discourse/temporal evidence producer over numeric factor-role signatures,
  explicit processed/sufficient/resolved consumer horizon outcomes,
  residual-driven H3/H6 advancement, evidence-polarity classification, and a
  zero-work success path for H9 consumers with no explicit external needs.
- `111_identity_witness_demand_support_projection.sql` leaves immutable identity
  witnesses untouched while deriving demand attribution only from explicit
  witness provenance, exact source-object equality, or exact shared parser-token
  representation support; accepted-use attribution still requires admission.
- `116_external_request_digest_smallint_fix.sql` preserves the provider-request
  digest layout while keeping nullable SMALLINT axis coordinates typed through
  `COALESCE`.
- `112_consumer_observed_world_axis_contract.sql` adds sparse consumer/query/policy
  contracts that declare which world coordinate can actually be observed and
  which numeric demand coordinates it applies to. Only the intersection with the
  live H9 residual becomes an external need; a contract cannot implicitly select
  every H9 demand. Manual and contract-derived need origins remain independent.
- `113_external_request_observer_lifecycle.sql` makes provider request liveness
  depend on active semantic observers. Requests with no active observer become a
  distinct dormant state, and completion/cache wakeup cannot resurrect withdrawn
  consumer fibres.
- `114_dormant_external_request_reprobe.sql` immediately re-probes a dormant
  request against local cache when an observer becomes active again, avoiding a
  second planner pass before cache-hit wakeup or provider leasing.
- `115_immutable_world_axis_contract_revisions.sql` makes each world-axis contract
  revision semantically immutable: changing selectors, provider coordinates,
  priority or freshness requires a new revision; same-revision re-registration
  may only toggle whether that revision is currently active.
- See `docs/reopenable_runtime_architecture.md`,
  `docs/consumer_sufficient_numeric_runtime.md`,
  `docs/late_external_provider_runtime.md`, and
  `scripts/audit_reopenable_runtime_migrations.py` for architecture and audits.

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
