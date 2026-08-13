# Late external-provider runtime

The strict numeric document compiler does not call Wikidata or any other external
provider. It closes the local numeric PNF, publishes residual demands, and records
`world_resolution_deferred = True` / `network_performed = False`.

External acquisition is a later consumer-triggered H9 operation:

```text
spaCy
  -> numeric PNF
  -> H3 local structural evidence
  -> consumer sufficiency
  -> unresolved consumer residual only -> H6
  -> consumer sufficiency
  -> unresolved world-observable residual only -> H9 external needs
  -> local candidate/evidence cache probe
  -> deduplicated cache misses only -> provider microbatch
  -> immutable external evidence cache
  -> affected H9 fibres only
```

## Call economy

A provider call is not generated from a proper noun. The consumer/query/policy
must register an explicit external need:

- candidate discovery;
- one property/axis enrichment need; or
- proof-producing identity alignment.

Property needs are keyed at provider-native granularity, for example Wikidata
`(Q, P)` coordinates. Multiple semantic demands and mentions can therefore be
members of one physical external request.

The planner probes the local label-candidate fibre, immutable external property
evidence, and admitted canonical world alignment before provider leasing. Only
true misses become provider-ready. Expired leases are re-probed before retry.

The empirical observatory reports both semantic fan-in and literal acquisition
calls. A warm resident Zelph query may consume zero external object reads, an HF
partial load may consume several shard reads, and a live HTTP/SPARQL request may
consume a different amount again. Wall time therefore remains a separate metric.

## Consumer-observed world-axis contracts

H9 readiness is not external work. It is only permission for a consumer to ask
whether its unresolved fibre observes a world coordinate.

Migration 112 adds a cold control-plane contract keyed by
`(consumer_ref, query_ref, policy_ref, contract_ref, revision)`. A contract names
one external need kind/provider coordinate and at least one numeric demand
selector drawn from the existing PNF demand carrier:

- expected target kind;
- expected factor type SymbolId;
- expected object kind SymbolId;
- lexical SymbolId;
- role SymbolId; or
- residual type SymbolId.

At least one selector is mandatory. There is deliberately no contract meaning
"all H9-ready demands" by omission.

Compilation is therefore the intersection

```text
current H9 residual
  ∩ current active consumer world-axis contracts
  ∩ exact numeric demand selectors
  -> explicit external needs
```

and an empty contract set compiles to zero external needs. The hot matching path
never resolves selector text or performs regex/semantic string matching.

Manual exact-demand needs remain supported. Manual and contract-derived origins
are tracked separately, so withdrawing one contract cannot disable an
independently registered need. Active need state, priority and freshness are the
exact projection over current active origins: any active origin keeps the need
live, the minimum priority wins, and the strongest freshness floor wins.

Contract revisions are semantic control history. Migration 115 makes a revision
immutable: changing selectors, provider/property coordinates, priority or
freshness requires a new revision. Re-registering the same revision may only
change whether it is active.

## External request observer lifecycle

Physical provider work is downstream of active semantic observation. Migration
113 adds request state `8 = dormant` for a request that has historical members
but no currently active semantic need.

This matters when a consumer narrows or withdraws a contract after work has
already been planned or leased:

```text
active need -> provider-ready/leased request
contract withdrawn
  -> semantic need inactive
  -> request dormant
  -> no hot materialisation
  -> no H9 wakeup
```

If a provider result arrives after withdrawal, its immutable cold evidence may
still be retained, but completion fails closed with respect to the withdrawn
consumer. Historical request-member rows remain provenance, not execution
authority.

When an observer later becomes active again, migration 114 reopens the dormant
request and immediately re-probes local cache in the same planning pass. Cached
evidence can therefore satisfy the reactivated need without another acquisition;
otherwise the request becomes provider-ready again.

## Discovery before enrichment

If a label has no candidate fibre, the planner emits only one deduplicated
candidate-discovery request. It does not eagerly request properties.

After candidate discovery is cached and H9 resumes, an explicit property need may
produce property requests only for candidates already in the local fibre. A
consumer needing country and administrative region therefore asks only the
provider properties mapped to those axes rather than downloading every property
of every candidate.

## Provider boundary

Database-local surrogates never escape to the provider adapter.

Candidate discovery receives boundary text such as `Springfield`. Entity/property
enrichment receives provider-native numeric coordinates such as Wikidata Q/P
integer payloads. Provider results likewise return provider-native ids and are
interned into PostgreSQL-local ids only after crossing that boundary.

Migrations 100 and 104 jointly guard this boundary. Migration 104 appends a
freshness floor to the lease projection without re-exposing `label_symbol_id` or
`world_entity_id`.

## Wikidata adapter

`src.policy.wikidata_late_provider.WikidataLateProvider` sits above an injected
`WikidataTransport`.

The provider deduplicates repeated labels and repeated `(Q,P)` property requests.
It additionally groups a microbatch by `minimum_source_epoch`, so a single
freshness-sensitive request does not force unrelated historical/static requests
through the live tier.

Ordinary Wikidata lookup is not identity proof. `IDENTITY_ALIGNMENT` is currently
rejected with `wikidata:identity-proof-adapter-required` and zero network calls.
Only a future proof-producing adapter may enter the existing external identity
admission lane.

## Zelph/Hugging Face snapshot tier

The repository already has Zelph/Wikidata integration and the ITIR parent owns
Zelph-HF manifest/shard routing and partial-load tooling. The late runtime reuses
that architecture through `ZelphSnapshotQueryBackend`; it does not introduce a
second graph store or duplicate the ITIR shard transport.

A Zelph/HF Wikidata rip is an **acquisition source**, not another entity namespace:

```text
Q408 from Zelph/HF == Q408 from live Wikidata
```

at the world-coordinate layer. Acquisition source, revision and source epoch are
separate immutable provenance.

The normal source ladder is:

```text
PostgreSQL evidence/candidate cache
  -> Zelph/HF Wikidata snapshot
  -> live Wikidata only for uncovered or too-old residuals
```

The current hosted snapshot is expected to be around June 2026, but runtime code
does not hard-code that date. `LateWikidataExecutor.zelph_snapshot_first()`
requires the caller to supply `snapshot_epoch` from the actual HF manifest or
artifact metadata. A snapshot whose epoch is below a request's freshness floor is
skipped **before** any Zelph/HF acquisition I/O.

This gives three distinct cases:

```text
freshness-insensitive historical/static query
  -> June snapshot may satisfy it

minimum_source_epoch <= snapshot_epoch
  -> snapshot may satisfy it

minimum_source_epoch > snapshot_epoch
  -> snapshot performs zero reads for that request; live tier gets the residual
```

`WikidataTierPolicy.require_live_*` remains available for consumers that require a
live recheck even when a snapshot is technically new enough.

When live evidence agrees with snapshot evidence, semantic interpretation may
collapse the values, but the older and newer provenance witnesses remain
separate. New evidence does not rewrite the snapshot receipt.

## Persisted freshness semantics

Migrations 103-104 make freshness part of H9 execution rather than a Python-only
preference.

- `semantic_pnf_consumer_external_need.minimum_source_epoch` expresses the
  consumer/query/policy freshness floor.
- `semantic_pnf_external_request.minimum_source_epoch` is the strongest floor of
  all member fibres sharing that physical request.
- candidate fibres and external property evidence carry their own source epochs.
- unknown-age legacy rows cannot satisfy a positive freshness requirement.
- tightening an already-existing need propagates to already-existing request
  members and reopens only the affected request.
- an equal or weaker requirement does not reopen work.

This preserves deduplication while preventing a stale-but-useful snapshot from
prematurely stopping a freshness-sensitive consumer.

## Benchmark gate

`scripts/benchmark_wikidata_source_tiers.py` runs the same label and `(Q,P)`
workload through snapshot-only, snapshot-then-live and live-only transports. It
reports median/min/max wall time, candidate/property hit fractions, acquisition
call counts, and accepts `--minimum-source-epoch` to measure the cost of a
freshness requirement directly.

The preferred first target is the pruned Zelph snapshot, but that is an empirical
optimization, not a semantic preference. Compare it against the full snapshot and
live transport on actual H9 residuals rather than raw graph-wide queries.

### Zelph shard planning boundary

The primary deployment target is a revision-pinned HF Zelph manifest, with a
local `.bin` artifact retained as an offline/reproducibility source. The current
public March 2026 pruned v2 manifest has no `nodeRouteIndex`; its legacy chunks
are therefore too coarse for one-process-per-label discovery. The CLI backend
loads only the name index for v2 discovery and batches all labels through one
Zelph process. It does not silently load adjacency sections for label lookup.

The ITIR shard studies measured approximately 21.70 MiB median and 41.57 MiB
p95 for v2 route-name loads, and approximately 51.95 MiB median and 60.63 MiB
p95 for two-sided route-node loads. Those values are a transport-cost
observation, not a semantic result. The planned v3 query-shaped bucket layout
and route sidecar remain the optimization path for a newer full HF rip. Until a
route-aware manifest is selected, the runtime records the coarse-v2 fallback
explicitly rather than presenting it as an optimal shard plan.

## External evidence

Provider facts are immutable cache rows. An evidence digest is idempotent and a
repeat observation never rewrites the original evidence provenance.

A property fact is not automatically a type assertion or identity assertion.
Symbol-valued, axis-typed evidence can become contextual requirements, which
remain pressure rather than identity proof. The same cached provider fact may be
re-projected under another consumer axis without another provider call.

Entity-valued and numeric facts remain cached until an explicit adapter supplies
the consumer representation needed to use them. Absence of a returned fact is not
semantic refutation.

## Execution boundary

`LateExternalHorizonExecutor.plan_h9_observed_world_axes()` is the preferred
consumer-contract entrypoint. It compiles the current active world-axis contracts
against one document's live H9 residual, then invokes the existing cache/request
planner. It performs no provider calls itself.

`LateExternalHorizonExecutor.plan_h9_external_residual()` remains available for a
caller that already possesses exact demand IDs and explicitly registers those
needs directly.

Actual calls happen only through `execute_external_provider_batch()` after the
PostgreSQL cache probe has leased provider-ready misses.

The intended empirical asymmetry remains:

```text
N_fresh_provider_calls << N_external_needs << N_H9_residual << N_mentions << N_tokens
```

for recurring-domain corpora when the consumer contracts and cache are effective.
This is an empirical target, not an unconditional theorem.
