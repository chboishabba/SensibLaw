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
| cold Gate-A functional | closed | complete direct end-to-end execution exists |
| cold Gate-A performance | open | system optimization continues, but is not a semantic prerequisite for G3/G4 certification |
| G5/G6 streaming/delta hierarchy | next architecture tranche | consume semantic work alongside parser progress and propagate only affected deltas |

## Last measured cold direct checkpoint

Fresh isolated workload:

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
previous green direct baseline.  Keep that work.

However, this measurement also shows that `2x parser time` is a **whole-system
milestone**, not a prerequisite that should block the architecture roadmap.
Even eliminating hierarchy completely would leave publication far above that
budget, while eliminating publication completely would still leave parser plus
hierarchy above `2x` on this run.

Therefore do not spend indefinite effort shaving the cold publication path
before implementing the mechanisms intended to overlap and avoid work.

## Revised highest-alpha order

```text
bank G1/G2/G4a + measured partition publication win
    -> bounded G3 direct/reference parity
    -> direct production cutover
    -> certify production G4b
    -> stream semantic execution alongside parser availability
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

`src/pnf/streaming_semantic_pacman.py` is the runtime strategy kernel for this
law.  It intentionally stores no parser-event history.

## Feed-point reality

The existing PostgreSQL streaming spaCy worker currently obtains a completed
bounded spaCy `Doc` from `pipeline.pipe(...)`, then projects/commits it and
runs PNF closure.  That is streaming at partition granularity, not yet at the
final semantic event granularity.

Do not fake finer streaming by creating a second parser or second PNF graph
implementation.  Move the feed point earlier only when the canonical parser
adapter can expose a stable event/prefix carrier whose consumer-visible meaning
is preserved.

Until then, completed-Doc or sentence batches are valid *physical fusions* of
the same streaming fold.

## Performance receipts for G5/G6

The streaming programme should add at least:

```text
stream_work_units
tail_work_units
stream_completion_fraction
frontier_size_at_EOF
tail_wall_time
semantic/parser overlap wall time
affected hierarchy boundaries
avoided unchanged relation writes
```

The intuitive target `stream_completion_fraction >= 0.8` is initially an
engineering objective only.  It is not a correctness gate.

Warm/incremental execution must be measured separately from cold ingestion.
The architecture should eventually make the important cost proportional to the
affected frontier rather than the total pre-existing document state.

## Never regress these invariants

- no second semantic compiler;
- no parser-token surrogate as direct semantic identity;
- no sentence-local PostgreSQL requirement;
- no full prefix/history replay for each new parser observation;
- no hierarchy rescan merely to discover whether an outward delta exists;
- no production cutover without consumer-visible direct/reference parity;
- no benchmark result redefining semantic authority.
