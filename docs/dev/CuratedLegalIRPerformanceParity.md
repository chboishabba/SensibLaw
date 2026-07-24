# Curated Legal-IR Performance and Parity

## Status

This document describes the implemented offline product path. It is not a
second legal parser or semantic compiler. All substantive documents use the
existing fibred PNF compiler and its single deterministic reduction boundary.

```text
persisted source catalogue
→ immutable source-admission receipt
→ canonical/fibred PNF compilation
→ explicit normative interaction demand
→ compatible persisted legal-source selection
→ legal-source fibred PNF
→ Legal IR projection
→ candidate-only typed meet
→ legacy diagnostic differential
→ parity and network-absence receipts
```

## Source admission

Admission occurs before parser submission and has three states:

```text
compile        substantive source; may enter canonical parsing

evidence_only discovery/transport evidence; retained but never parsed

exclude        duplicate, unrelated, unknown, or otherwise ineligible artefact
```

Every inventoried revision receives an immutable receipt containing its source
role, semantic scope, profile revision, state, and reason. Unknown roles fail
closed. The HCA regression profile admits substantive transcripts, judgments,
submissions, chronologies, appeal/reply/outline documents, and genuine
transcript media. Search, navigation, database, landing, OEmbed, and recording
pages are evidence-only. Duplicate captions and unrelated support material are
excluded.

The catalogue command has no acquisition capability. `--force-refetch` is
rejected. It copies only declared persisted source families and writes:

- `source_admission_manifest.json`;
- `network_absence_receipt.json`;
- `document_compilation_timings.json`;
- `catalogue_build_manifest.json`.

## Governed acquisition

Network acquisition is a separate operator effect:

```text
scripts/acquire_legal_source.py
```

It requires:

- an operator authorization reference;
- a provider profile;
- an allow-listed host;
- a byte bound;
- permitted media types;
- declared jurisdiction, source role, and authority level.

The result is content-addressed, admitted under the primary-law profile, and
registered as a persisted legal-source revision. Acquisition receipts retain
network and provider provenance but cannot promote identity, applicability, or
legal truth.

A normal semantic build can only emit a blocked acquisition requirement. It
cannot call the acquisition operation.

## Persisted legal-source planning

`NormativeInteractionDemand` is projected only from explicit legal PNF pressure
or an explicit operator request. The durable registry is queried by:

- jurisdiction;
- source role;
- authority level;
- provider profile where requested;
- temporal compatibility where represented;
- compile eligibility.

A `LegalSourcePlan` is either:

```text
ready_persisted
blocked_missing_context
blocked_acquisition_required
```

`ready_persisted` means retrieval-compatible input is available. It does not
mean the source is applicable, controlling, correctly interpreted, or legally
true.

## Persistence execution

The immutable document transaction is split into measured groups:

```text
postgres.token_lexeme
postgres.graph_revision
postgres.resolution_binding
postgres.fibred_ledger
postgres.receipts
postgres_persistence
```

The implementation batches:

- unique lexeme insertion and one stable key-to-ID lookup;
- codec symbols and annotation nodes/relations;
- factors, revisions, graph membership, alternatives, and residuals;
- evidence, demands/facets, meets, and refinement transitions;
- binding anchors, morphology, candidate sets, members, exclusions, and links;
- observation deltas, proposals, jobs, receipts, state deltas, and boundaries;
- fibre coordinates, elements, derivations, transports, ontology axes,
  obligations, summaries, and producer receipts.

Foreign-key order remains deterministic. The persisted integrated-producer
receipt must reproduce the compiler's in-memory fibre-ledger and receipt
identities before the completed-build receipt is committed.

Deadlock (`40P01`) and serialization (`40001`) failures retry the whole immutable
document attempt with bounded deterministic delay. Attempt number, SQLSTATE,
worker, and delay are execution telemetry and do not enter semantic or build
identity.

## Fibre-local proposal reduction

Exact proposals are deduplicated and then partitioned by:

```text
semantic coordinate
+ fibre kind
+ factor type
+ structural signature
```

Compatibility grouping occurs only within a bucket. The graph and factor
identity formulas are unchanged. Execution-only metrics include:

- bucket count and largest bucket;
- actual and potential candidate comparisons;
- comparisons avoided and avoidance ratio;
- duplicates collapsed;
- alternatives retained;
- factor count and reduction ratio.

Metrics are excluded from graph identity.

## Offline parity proof

```text
scripts/run_curated_legal_ir_parity.py
```

The parity runner:

1. admits and compiles ordinary HCA/case sources through fibred PNF;
2. projects explicit legal demands;
3. queries the persisted legal-source registry;
4. preserves missing sources as blocked acquisition requirements;
5. compiles selected legal sources through the same fibred compiler;
6. projects Legal IR;
7. constructs candidate-only typed meets;
8. runs the existing legacy obligation extractor only as a diagnostic witness;
9. retains comparison and PNF coverage ledgers;
10. records semantic identity and optional control-run parity;
11. rejects external network attempts.

The semantic identity snapshot contains proposal, factor, graph, fibre-ledger,
residual, demand, Legal IR, typed-meet, and legacy-witness references. Timing,
retry, worker, and SQL execution receipts are intentionally absent.

A zero-Legal-IR result or blocked source plan is an empirical coverage result.
The parity runner never invents applicability to make the scorecard non-zero.

## Acceptance evidence

The curated run should retain:

- exact source and profile revisions;
- admission manifest;
- fixed-point certificates;
- nested stage timings;
- reducer bucket/comparison metrics;
- transaction-attempt receipts;
- ordinary and legal graph identities;
- blocked acquisition requirements and selected-source plans;
- Legal IR, typed meets, and legacy comparison ledgers;
- identity parity result;
- external-network-absence receipt.

Performance thresholds are evaluated on a fixed small/medium admitted source
set with compiler, profile, worker, PostgreSQL, and cache conditions recorded.
No threshold permits semantic identity drift.

## Authority boundary

```text
admission receipt       catalogue policy only
source selection plan   retrieval compatibility only
Legal IR                deterministic PNF projection only
typed meet              structural comparison only
legacy witness          diagnostic evidence only
parity receipt          audit evidence only
```

None closes identity, applicability, breach, liability, or legal truth.
