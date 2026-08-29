# Streaming semantic Pac-Man kernel

Status: normative execution target for the direct packed-fibre PNF runtime.

This document names the temporal execution model that SensibLaw should converge
on.  It does **not** create a new semantic compiler.  Existing numeric PNF
composition remains authoritative; this architecture changes when that work is
performed and how little unresolved state is carried forward.

## Formal owners

Before modifying this runtime, inspect the corresponding DASHI Agda owners in
`chboishabba/dashi_agda`, branch `agent/delta-native-parent-frontier` (or their
newer promoted equivalents):

- `DASHI/Cognition/PNF/StreamingSemanticPacmanKernelExact.agda`
- `DASHI/Cognition/PNF/StreamingPhysicalOverlapReceiptExact.agda`
- `DASHI/Cognition/PNF/DeltaNativePNFDreamFlowExact.agda`
- `DASHI/Cognition/PNF/FibreSolverDeltaStreamExact.agda`
- `DASHI/Cognition/PNF/DirectDeltaCompilerArchitectureExact.agda`
- `DASHI/Cognition/PNF/DirectDeltaCompilerActivationExact.agda`
- `DASHI/Cognition/PNF/DirectStreamingRoadmapSynthesisExact.agda`

If code and these formal owners disagree, do not silently pick one. Record the
mismatch and repair the bridge or the stale side explicitly.

## Core law

Let `p` be an already-consumed ordered parser prefix and `q` a later suffix.
The semantic state after the whole stream must be obtainable by continuing from
the prefix state:

```text
state(prefix ++ suffix) = continue(state(prefix), suffix)
```

Equivalently, in the delta-native formulation:

```text
S[p ++ q] = apply(S[p], Delta(q))
```

A consumed parser prefix is therefore never rescanned merely because later
parser observations arrive.

Physical batching is allowed. A parser partition, sentence tranche, SIMD/SWAR
batch, or another bounded execution unit may fuse adjacent events as long as
ordered semantic composition is unchanged.

## The Pac-Man state

The streaming execution state is intentionally small:

```text
K_t = (
    current semantic authority,
    unresolved outward frontier,
    stable evidence / source identities,
    diagnostic work counters
)
```

It is **not**:

```text
K_t = all previous parser events + a promise to compile them later
```

Resolved events disappear into current authority. Only unresolved forward
obligations remain on the frontier.

Examples of legitimate frontier members include:

- a dependency whose head/complement is not yet available;
- a boundary crossing that needs the neighbouring owned fibre;
- an unresolved candidate alternative whose discriminator has not arrived;
- an outward child-to-parent semantic delta awaiting an affected boundary;
- a sentence-close obligation that genuinely cannot be determined earlier.

The frontier must not become a disguised copy of the sentence or document.

## Runtime shape

The target steady-state execution loop is:

```text
spaCy/parser observation becomes stable
        |
        v
assign local typed/source identity
        |
        v
update packed local fibre
        |
        v
run existing semantic owner / emit ordinary delta
        |
        v
apply delta to current authority
        |
        v
resolve newly satisfiable dependencies
        |
        v
retain only unresolved outward frontier
        |
       repeat
```

At sentence or parser-stream close:

```text
finalize(frontier)
    -> close genuinely unresolved boundaries
    -> emit final outward hierarchy deltas
    -> stage/publish durable authority
```

End-of-stream must **not** mean "start semantic compilation now".

## Current implementation seam

`src/pnf/streaming_semantic_pacman.py` is the pure execution kernel. It is a
strategy layer around the existing semantic authority. It stores no parser
history and exposes:

- ordered `consume(event)`;
- associatively fused `consume_many(events)`;
- a current authority/frontier snapshot;
- `finalize()` for residual tail work only;
- work accounting for stream-vs-tail measurement.

`src/runtime/overlapped_parser_semantic_stream.py` is the first physical overlap
owner. It runs the canonical parser producer in one thread and exposes a bounded
ordered queue to the existing direct semantic/publication consumer. The queue
is intentionally small (Gate-A uses one item), so parser output cannot become
an unbounded retained history. Consumer failure/early-stop signals cancellation
back to the producer.

The direct Gate-A path now uses this overlap:

```text
spaCy parses partition n+1
          ||
          || overlap
          \/
direct packed-fibre compile/publication consumes completed partition n
```

`commit_direct_partition` remains the existing semantic/publication owner. The
overlap layer never constructs its own objects/factors/demands and therefore is
not a second compiler.

### Current granularity and next feed point

spaCy still yields a completed bounded `Doc` for each parser partition. Thus the
implemented overlap is **partition-fused streaming**, not yet token/dependency
event streaming. This is a legitimate physical fusion of the formal ordered
fold and already removes the previous barrier where the benchmark materialised
all leased parsed partitions before beginning direct work.

The next evolution is to move the feed point earlier only when the canonical
parser adapter can expose stable prefix/events whose consumer-visible meaning is
well-defined. Keep the same semantic owner and Pac-Man state when that happens.

Do **not** implement a second token-by-token graph compiler merely to claim
streaming.

## Relationship to packed fibres and G1-G4

The packed/direct programme remains:

```text
G1  parser observations -> DB-neutral typed packed fibre
G2  fibre -> existing numeric sentence composition, local DB crossings = 0
G3  direct/reference consumer-observation parity, fail closed
G4  durable stable-evidence authority, production parser-token writes = 0
```

The Pac-Man kernel is the temporal synthesis of G1/G2 with the delta-native
G5/G6 destination. It does not weaken G3 or G4 and does not make parser-token
surrogates semantic identity.

PostgreSQL is the durable/global/publication boundary, not the mandatory
internal execution bus.

## Performance objective

"80% solved by spaCy EOF" is a useful engineering intuition, not a theorem.
Measure it.

At minimum record:

```text
W_stream = semantic work performed while parser observations are consumed
W_tail   = semantic work after parser/event EOF
fraction = W_stream / (W_stream + W_tail)
```

The initial aspiration may be `fraction >= 0.8`, but correctness must never
depend on that threshold.

The overlapped Gate-A receipt adds concrete physical measurements:

```text
parser_semantic_overlap_ns
semantic_sentences_at_parser_eof
stream_completion_fraction
post_parser_tail_ns
phase_accounting = overlapped_active_time
```

Because parser and publication active intervals now overlap, their active-time
fields are not expected to sum to total wall time. End-to-end `direct_total_ns`
remains the comparable wall-clock metric.

Wall time should converge toward:

```text
T_direct ~= max(T_parser, T_semantic_stream) + T_tail + T_publication_boundary
```

rather than:

```text
T_direct = T_parser + T_full_semantic_compile + T_full_hierarchy + T_publish
```

For warm/delta execution also report affected-frontier work and avoided work,
not merely a cold full-build ratio.

## Roadmap position

The current recommended order is:

```text
bank the proven direct architecture and measured publication improvements
    -> bounded G3 parity corpus
    -> promote direct production authority / certify production G4
    -> expand the implemented parser/semantic overlap toward stable event prefixes
    -> make hierarchy/reconciliation delta-native over affected boundaries
    -> benchmark cold and incremental execution
    -> revisit deeper persistence batching only if it remains dominant
```

Do not require endless cold-publication micro-optimization before advancing to
streaming/delta hierarchy. Benchmarks prioritize implementation work; they do
not redefine the semantic architecture.

## Acceptance tests for future streaming work

A change claiming to advance this architecture should prove as many of these as
apply:

1. Prefix + suffix execution equals one fused ordered execution.
2. The kernel does not retain/replay already-consumed parser history.
3. Only unresolved obligations remain in the frontier.
4. A closed frontier means no remaining outward semantic delta, not "rescan was
   successful".
5. Physical partitioning changes scheduling only, not semantic observations.
6. Stable evidence identities survive publication reindexing.
7. Sentence-local database crossings remain zero.
8. Production direct mode does not require parser-token rows.
9. Stream/tail work and parser/semantic overlap are measured separately.
10. Consumer-visible direct/reference parity remains the production cutover
    authority.
11. Parser/semantic overlap remains bounded and consumer cancellation cannot
    strand a producer behind retained parser history.
