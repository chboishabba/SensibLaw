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

The external request digest is computed before provider leasing. The planner then
probes:

1. the local label -> world-candidate fibre;
2. the immutable external property-evidence cache; and
3. admitted canonical world alignment for explicit identity needs.

Only true misses become `provider-ready`. Expired leases are cache-probed again
before retry, so another worker/document can satisfy a request while it is leased
without causing a duplicate network call.

The empirical observatory reports both semantic fan-in and literal provider calls:

```text
semantic_request_members / unique_external_requests
leased_request_attempts / fresh_provider_calls
```

`provider_call_count` is provider/acquisition I/O at the adapter boundary. A
request may fail locally with zero calls (for example, identity alignment when no
proof adapter exists). Transport-specific benchmarks must additionally measure
wall time because one warm local Zelph query, one HF shard acquisition, and one
live HTTP/SPARQL request do not have equal cost.

## Discovery before enrichment

If a label has no candidate fibre, the planner emits only one deduplicated
candidate-discovery request. It does not eagerly request properties.

After candidate discovery is cached and H9 resumes, an explicit property need may
produce property requests only for the candidates already in that local fibre.
Thus a consumer needing country and administrative region can request exactly the
provider properties mapped to those axes rather than downloading every property
of every candidate.

## Provider boundary

Database-local surrogates never escape to the provider adapter.

Candidate discovery receives boundary text such as `Springfield`.
Entity/property enrichment receives provider-native numeric coordinates such as
`Q<n>` / `P<n>` represented by their positive integer payloads.

Provider results likewise use provider-native entity ids. The PostgreSQL gateway
interns those into `semantic_pnf_world_entity_numeric` before persistence. Textual
provider values cross only this explicit boundary and are interned through the
existing corpus-wide `numeric_symbol_store` machinery.

## Wikidata adapter

`src.policy.wikidata_late_provider.WikidataLateProvider` sits above an injected
`WikidataTransport`.

The provider adapter deduplicates:

- repeated search labels; and
- repeated `(Q, P)` property requests

before invoking transport methods. The transport reports its actual call count,
so an HTTP, REST, Action API, SPARQL, local mirror, or future federated transport
may choose the most efficient legal mechanism without changing semantic logic.

Ordinary Wikidata lookup is not identity proof. `IDENTITY_ALIGNMENT` is currently
rejected with `wikidata:identity-proof-adapter-required` and zero network calls.
Only a future proof-producing adapter may enter the existing external identity
admission lane.

## Zelph/Hugging Face snapshot tier

The repository already has Zelph/Wikidata integration and the ITIR parent owns
Zelph-HF manifest/shard routing and partial-load tooling. The late runtime reuses
that architecture through `ZelphSnapshotQueryBackend`; it does not introduce a
second graph store or duplicate the ITIR shard transport.

A Zelph/HF Wikidata rip is an **acquisition source**, not another entity
namespace. Therefore:

```text
Q408 from Zelph/HF == Q408 from live Wikidata
```

at the world-coordinate layer, while the immutable evidence receipt retains its
acquisition source and revision.

The normal source ladder is:

```text
PostgreSQL evidence/candidate cache
  -> Zelph/HF Wikidata snapshot
  -> live Wikidata only for snapshot misses or explicit freshness requirements
```

`WikidataTierPolicy` makes freshness visible rather than implicit:

- `fallback_on_snapshot_miss=True`: normal cheap path;
- `require_live_discovery=True`: live candidate discovery even after a snapshot hit;
- `require_live_properties=True`: live property recheck even after a snapshot hit.

When a freshness-required live fact agrees with a snapshot fact, the value may be
semantically equivalent but the two provenance witnesses remain distinct. This
prevents a newer observation from silently rewriting the older snapshot receipt.

The first benchmark target should be the pruned Zelph Wikidata snapshot because
it is intended to be materially cheaper to keep resident than the full graph.
This is an empirical optimization, not a semantic preference. A consumer whose
answer depends on current world state must request the live tier regardless of
snapshot speed.

`LateWikidataExecutor.zelph_snapshot_first()` wires the tiered transport into the
existing deduplicated H9 worker. Strict document compilation remains network-free.

`scripts/benchmark_wikidata_source_tiers.py` runs the same label and `(Q,P)`
workload through:

1. snapshot-only;
2. snapshot-then-live; and
3. live-only.

It reports median/min/max wall time, candidate/property hit fractions and
acquisition-call counts. The decision to prefer the snapshot tier should be made
from those measurements on the actual GWB/archive workload, especially warm
resident performance and snapshot miss rate.

## External evidence

Provider facts are immutable cache rows. An evidence digest is idempotent and a
repeat observation never rewrites the original evidence provenance.

A property fact is not automatically a type assertion or identity assertion.
Symbol-valued, axis-typed evidence can be projected into
`semantic_pnf_world_candidate_requirement`, which remains contextual pressure.
The same cached provider fact may later be re-projected under another consumer's
axis interpretation; provider facts are not permanently owned by the first
consumer that acquired them.

Entity-valued and numeric facts remain cached until an explicit adapter supplies
the consumer representation needed to use them. Absence of a returned fact is not
semantic refutation.

## Execution boundary

`LateExternalHorizonExecutor.plan_h9_external_residual()` registers concrete
external needs and invokes planning only after a consumer has an H9 residual. It
performs no provider calls itself.

Actual calls happen only through `execute_external_provider_batch()` after the
PostgreSQL cache probe has leased provider-ready misses.

This preserves the intended asymmetry:

```text
N_fresh_provider_calls << N_external_needs << N_mentions << N_tokens
```

for recurring-domain corpora when the cache is effective. This is an empirical
target, not an unconditional theorem; migrations 098-101 persist the receipts
needed to measure it.
