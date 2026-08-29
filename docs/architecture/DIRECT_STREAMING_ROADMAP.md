# Direct packed-fibre / streaming semantic roadmap

Status: current implementation roadmap for `agent/packed-a2-swar`.

Formal companion: `chboishabba/dashi_agda`, currently
`agent/delta-native-parent-frontier` until promoted.

Read this together with `STREAMING_SEMANTIC_PACMAN.md` and the Agda modules
listed there before changing parser/direct-PNF execution.

## Current gate state

| Gate | State | Runtime meaning |
| --- | --- | --- |
| G1 packed parser fibre | closed | parser observations have DB-neutral typed/local carriers |
| G2 direct semantic compiler | closed | existing numeric PNF composition runs with sentence-local DB crossings = 0 |
| G3 direct/reference parity | executable, not production-certified | bounded consumer-observation parity corpus and fail-closed router promotion remain |
| G4a stable evidence/provenance | closed for direct execution | stable evidence is durable semantic support; direct runs require no parser rows |
| G4b production parser-token retirement | pending cutover | certify parser-token writes = 0 on the public production authority after G3 |
| cold Gate-A functional | closed on pre-overlap head | complete direct end-to-end execution exists; revalidate after overlap changes |
| parser/direct partition overlap | implemented, awaiting fresh receipt | completed partition `n` is consumed while spaCy parses partition `n+1` through a bounded one-item queue |
| event-level Pac-Man feed | open | move feed point earlier only when canonical parser adapter exposes stable prefix/event semantics |
| delta-native hierarchy | next architecture tranche | propagate only affected outward deltas/frontiers rather than broad post-parse rescans |

## Last measured cold direct checkpoint

The last **measured** green checkpoint predates the new parser/semantic overlap
implementation. Fresh isolated workload:

- 247 sentences;
- 12,750 tokens;
- 4 parser partitions;
- complete coverage;
- zero local DB crossings;
- zero parser sentence/token/entity rows;
- 12,750 stable evidence rows.

After the retained partition control-plane tranche:

```text
spaCy/parser             ~3.085 s
local publication       ~17.877 s
hierarchy/reconcile      ~6.195 s
direct total            ~27.157 s
direct/parser ratio       ~8.80x
```

The control-plane tranche reduced publication by about 12.4% relative to the
previous green direct baseline. Keep that work.

Do **not** compare the old `local publication` field mechanically with the new
overlap receipt. Under overlap, parser and publication active times can overlap
and therefore do not sum to wall time. `direct_total_ns` remains directly
comparable; the new receipt explicitly reports `phase_accounting =
overlapped_active_time`.

This checkpoint already showed that `2x parser time` is a **whole-system
milestone**, not a prerequisite that should block the architecture roadmap.
Therefore do not spend indefinite effort shaving the cold publication path
before implementing the mechanisms intended to overlap and avoid work.

## Revised highest-alpha order

```text
bank G1/G2/G4a + measured partition publication win
    -> bounded G3 direct/reference parity
    -> direct production cutover
    -> certify production G4b
    -> validate/expand implemented parser-semantic overlap
    -> expose stable earlier parser events/prefixes when canonical parser permits
    -> delta-native affected-boundary hierarchy/reconciliation
    -> benchmark cold + incremental/warm execution
    -> revisit partition-keyed graph/provenance persistence only if still dominant
```

This ordering is mirrored by
`DASHI/Cognition/PNF/DirectStreamingRoadmapSynthesisExact.agda`.

## Streaming target

Do not conceptualize the runtime as:

```text
parse entire input
    -> begin semantic compilation
    -> begin hierarchy
    -> publish
```

The target is:

```text
parser event/prefix becomes stable
    -> consume it immediately into current semantic authority
    -> emit/apply ordinary semantic delta
    -> resolve newly satisfiable local obligations
    -> retain only unresolved frontier
    -> continue with later parser observations
```

At parser EOF, most normal semantic work should already have been consumed.
The tail is limited to unresolved forward/boundary obligations, final outward
deltas, and durable publication.

The exact semantic law is:

```text
state(prefix ++ suffix) = continue(state(prefix), suffix)
```

`src/pnf/streaming_semantic_pacman.py` is the pure runtime strategy kernel for
this law. It intentionally stores no parser-event history.

## Implemented overlap layer

`src/runtime/overlapped_parser_semantic_stream.py` provides a bounded ordered
producer/consumer bridge. In the direct Gate-A path:

```text
producer thread:  canonical spaCy pipeline.pipe(...)
                        |
                        v
                  queue(maxsize=1)
                        |
                        v
consumer:         commit_direct_partition(...)
```

This means a completed parser partition is consumed immediately while spaCy is
allowed to work on the next partition. The queue bound prevents completed
parser output from becoming retained history. Consumer failure/early-stop
signals cancellation to the producer.

The semantic owner remains `commit_direct_partition` -> packed fibre -> existing
numeric sentence composition. The overlap helper owns scheduling only.

## Feed-point reality

The current parser still exposes a completed bounded spaCy `Doc` as the stable
unit. Therefore the implemented runtime is **partition-fused Pac-Man streaming**,
not yet token/dependency-event streaming.

That is a deliberate intermediate point. Do not fake finer streaming by
creating a second parser or PNF graph implementation. Move the feed point earlier
only when the canonical parser adapter can expose a stable event/prefix carrier
whose consumer-visible meaning is preserved.

Completed-Doc, sentence, SWAR, or partition batches are valid physical fusions
of the same ordered delta fold.

## Performance receipts for G5/G6

The direct overlap benchmark now reports:

```text
parser_semantic_overlap_ns
semantic_sentences_at_parser_eof
stream_completion_fraction
post_parser_tail_ns
phase_accounting = overlapped_active_time
```

The broader streaming programme should additionally converge on:

```text
stream_work_units
tail_work_units
frontier_size_at_EOF
affected hierarchy boundaries
avoided unchanged relation writes
```

The intuitive target `stream_completion_fraction >= 0.8` is initially an
engineering objective only. It is not a correctness gate.

Warm/incremental execution must be measured separately from cold ingestion.
The architecture should eventually make the important cost proportional to the
affected frontier rather than the total pre-existing document state.

## Never regress these invariants

- no second semantic compiler;
- no parser-token surrogate as direct semantic identity;
- no sentence-local PostgreSQL requirement;
- no full prefix/history replay for each new parser observation;
- no unbounded parser-output queue masquerading as streaming;
- no hierarchy rescan merely to discover whether an outward delta exists;
- no production cutover without consumer-visible direct/reference parity;
- no benchmark result redefining semantic authority.
