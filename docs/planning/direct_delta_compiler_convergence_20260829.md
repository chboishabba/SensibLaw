# Direct Delta Compiler convergence roadmap

Status: active programme roadmap for the strict numeric compiler.

Normative architecture: [Direct Delta Compiler Architecture](../architecture/DIRECT_DELTA_COMPILER_ARCHITECTURE.md).

This roadmap replaces bottleneck-by-bottleneck architectural discovery. Benchmarks now rank remaining violations of one declared target architecture. A tranche may be small for tool/runtime limits, but it must advance one or more finite convergence gates below.

## Programme outcome

The production path is complete when it has the shape:

```text
source -> bounded parser fibre -> packed structural fibre -> local semantic solve
       -> typed delta/residual -> affected-key transport -> document fixed point
       -> non-current semantic generation -> atomic authority publication
```

and the relational parser projection is no longer a mandatory semantic bus.

## Formal source of truth

The runtime architecture is constrained by DASHI. The big-picture formal owner is:

- [`DirectDeltaCompilerArchitectureExact.agda`](https://github.com/chboishabba/dashi_agda/blob/agent/delta-native-parent-frontier/DASHI/Cognition/PNF/DirectDeltaCompilerArchitectureExact.agda)

Aggregate/formal dependencies include `DreamFlowExecutionEverything`, `FibreSolverDeltaStreamExact`, `FibreNaturalDeltaTransportExact`, `SentenceParagraphNaturalDeltaExact`, `FibreLocalTokenAddressExact`, `FibreLocalPackedStorageExact`, `PackedNormativeDeltaAuthorityBridgeExact`, `SparseFibredFrontier`, `AffectedBoundaryLocalReductionExact`, `RelationDeltaReconciliationExact` and `DreamFlowRuntimeComplexityExact`.

Runtime work must not silently weaken those boundaries in order to win a benchmark.

## Frozen architectural gates

These are destination gates, not optional optimizations.

| Gate | Zero/acceptance condition |
| --- | --- |
| G0 single authority | no second semantic compiler or independent authority path |
| G1 parser seam | production spaCy output becomes packed/local structural fibre without mandatory parser-token SQL publication |
| G2 local solve | sentence-local deterministic PNF solving performs zero PostgreSQL crossings |
| G3 identity | local solving uses local/stable identity; database surrogates are resolved only for durable survivors at publication boundaries |
| G4 residual boundary | unresolved/ambiguous state crosses fibres as typed residuals/exports, not by reopening child interiors |
| G5 hierarchy | parent work consumes transported deltas/affected keys; ordinary closed-child interior reads are zero |
| G6 reconciliation | unchanged keyed relation members cause zero writes and zero manufactured transitions |
| G7 persistence | execution interior is not row-wise durable by default; compact checkpoint artifacts are available where resumability requires them |
| G8 generation staging | expensive computation may commit resumable non-authoritative staging independently of consumer-visible authority |
| G9 publication | closed/validated candidate generation becomes authority through a small atomic publication transition |
| G10 reference parity | direct packed path and SQL-reference path are consumer-equivalent on the certification suite |
| G11 observability | killed/rolled-back probes retain the same diagnostic dimensions as full runs and remain acceptance-ineligible |
| G12 representative acceptance | completed representative workload satisfies semantic gate and accepted timing ledger |

## Current state after probes 211/212

The short-run evidence established two useful facts without constituting final performance acceptance:

- deferred hierarchy publication removed the previous short-run hierarchy reconstruction pathology;
- restricting symbol advisory locks to unresolved symbols reduced synchronization pressure;
- PostgreSQL parser/token materialization remains the dominant short-run streaming cost.

Therefore the highest-cost current architectural violation is G1/G2: the parser substrate is still expanded into the relational token authority path before local semantic work can proceed.

Do not spend another tranche trying to make `semantic_parser_token` the ideal production inter-stage bus. Improve that path only as required for reference/audit parity. Production convergence removes the mandatory crossing.

## Tranche A — activate packed parser fibre as production execution carrier

Deliverables:

- direct adapter from spaCy observations to the already validated packed/local carrier;
- stable typed digests plus dense fibre-local IDs where useful;
- exact local head/dependency coordinates and explicit cross-fibre obligations;
- no read from `semantic_parser_token` to construct the local fibre;
- optional content-addressed packed checkpoint artifact.

Acceptance:

```text
ParserTokenWrites_production = 0
```

for the activated direct path, while parity/reference mode remains available.

## Tranche B — direct sentence-local PNF solve

Deliverables:

- at least one real production sentence-close reducer consumes the packed fibre directly;
- outputs typed semantic delta, residuals/demands, alternatives and exports compatible with current authority;
- sentence-local scratch/candidate state remains process-local unless it crosses a persistence cut.

Acceptance:

```text
DBCrossings_sentence_local = 0
```

for the closed local operation and no semantic mismatch against the reference solver.

## Tranche C — shadow direct/reference certification

Run both paths from the same packed fibre:

```text
packed fibre -> direct solve
            -> SQL reference projection -> reference solve
```

Compare consumer-visible authority, not physical surrogate IDs or timing coordinates.

Acceptance:

- deterministic outputs equal where exact equality is the declared semantics;
- relational/consumer-indexed outputs satisfy the existing consumer-equivalence relation;
- mismatch fails closed and preserves the reference path for diagnosis;
- GWB bounded shadow samples exercise actual production structures, not synthetic-only fixtures.

## Tranche D — direct sentence-to-parent delta transport

Deliverables:

- direct transport of emitted sentence boundary deltas/residuals to paragraph affected keys;
- no reread/reconstruction of the sentence interior;
- batch/fused child deltas where formal commutation/order conditions permit;
- propagation stops when parent observable boundary is unchanged.

Acceptance:

```text
ClosedChildInteriorReads_parent = 0
HierarchyWork = function(emitted deltas, hierarchy depth, bounded affected keys)
```

for the activated path.

## Tranche E — horizontal reconciliation conversion

Apply the existing desired/current delta algebra to every high-churn keyed current-state owner whose semantics permit exact keyed reconciliation.

Priority examples:

- candidate relations;
- parent exports;
- lookup projections;
- actor/action summaries;
- demand/resolution current state;
- adjacency current-state products;
- derived caches.

Acceptance:

```text
unchanged => zero writes
reconsideration != transition
```

Receipts must separate touched/reconsidered keys from emitted semantic changes and physical mutations.

## Tranche F — durable packed recovery boundary

Deliverables:

- content-addressed packed fibre/document artifact format or existing exact codec promoted to recovery use;
- PostgreSQL checkpoint stores digest/locator/run/partition/generation metadata, not mandatory row-wise parser interior;
- restart resumes local solve or transport from the artifact without reparsing when policy permits.

Acceptance:

- exact round trip;
- artifact corruption/mismatch fails closed;
- artifact durability does not imply semantic authority;
- recovery path preserves provenance and parser contract identity.

## Tranche G — generation-based semantic staging

Deliverables:

- candidate semantic generation namespace;
- short resumable transactions for deltas/residuals/provenance/checkpoints;
- current consumer-visible generation remains unchanged during construction;
- explicit validation/closure state.

Acceptance:

- crash before publication leaves previous authority intact;
- resumable staging can survive process failure;
- staging rows cannot be observed through ordinary current-authority queries.

## Tranche H — atomic publication

Deliverables:

- small publication transaction that promotes the validated/closed generation;
- global lookup/provenance publication derived from the promoted generation as required;
- rollback semantics and publication receipt.

Acceptance:

```text
Valid(G) and Closed(G) and Certified(G) => Publish(G)
```

and no partial generation becomes consumer-visible.

## Tranche I — global PostgreSQL placement audit

Classify every hot table/function/query by the four persistence cuts and PostgreSQL's five permitted jobs.

For each hot relation answer:

1. What object class is this: execution interior, durable non-authority evidence, or semantic authority?
2. Which persistence cut owns it?
3. Does the operation require operands from independently produced/committed fibres?
4. Could the operation execute inside one bounded local fibre instead?
5. If PostgreSQL remains, is the crossing fused/set-wise and justified by authority/global reconciliation/recovery/reference semantics?

Any hot operation with no coherent answer becomes a finite architecture gap.

## Tranche J — permanent diagnostic plane

Keep the rollback-independent observer and extend direct-path timing so every short probe and full run exposes the same dimensions:

```text
parser
packing/direct projection
local solve
transport
DB publication
reference-only work
CPU/RSS
DB waits/locks
SQL calls/rows/time
physical mutations
keys touched
unchanged skipped
semantic deltas emitted
```

Partial probes are always `acceptance_eligible=false`.

Use CPU flamegraphs only after CPU becomes a material fraction of wall time for an unexplained owner.

## Tranche K — production/reference mode switch and retirement gates

The SQL parser projection remains available during convergence.

Production direct mode may become default only after:

- required direct/reference parity suite passes;
- representative GWB direct run completes semantically;
- recovery/checkpoint path is proven sufficient;
- observability remains complete;
- no production consumer silently depends on relational parser interiors.

Reference/audit mode is retained unless separately deprecated; removing it is not required for production performance acceptance.

## Performance gates

Performance cannot certify correctness and partial timing cannot certify performance.

Staged goals:

1. architectural proof: local DB crossings and production parser-token writes reach zero on the direct path;
2. practical runtime gate: total strict execution <= 1.5x bare spaCy on the accepted representative workload;
3. long-term constitution: post-parser work <= 0.1x spaCy where achievable without semantic weakening.

The prior <=1.2x target remains a useful intermediate near-parity checkpoint, but the architectural counters above are the primary convergence tests.

## Work selection rule

Every new implementation task must state:

- which gate(s) G0-G12 it closes;
- the current runtime edge violating that gate;
- the formal owner(s) constraining the change;
- semantic pre/postconditions;
- physical work counters expected to change;
- rollback/reference strategy.

A benchmark may change priority but cannot create a competing architecture.

## Definition of done

The programme is done when all mandatory gates are green and the accepted representative run demonstrates the declared performance threshold with exact authority preserved.

At that point optimization becomes ordinary kernel engineering inside a stable architecture, not discovery of the compiler's execution model.
