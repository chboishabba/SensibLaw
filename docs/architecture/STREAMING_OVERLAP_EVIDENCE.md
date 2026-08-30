# Streaming overlap evidence

Status: normative measurement companion to `STREAMING_SEMANTIC_PACMAN.md`.

A high fraction of semantic work complete at parser EOF is **not** sufficient
evidence of useful parser/semantic overlap. Physical partition geometry, parser
batching, and authority parity must be checked separately.

## Formal owners

Before changing this experiment inspect:

- `DASHI/Cognition/PNF/StreamingSemanticPacmanKernelExact.agda`
- `DASHI/Cognition/PNF/StreamingPhysicalOverlapReceiptExact.agda`
- `DASHI/Cognition/PNF/StreamingPhysicalPartitionRefinementExact.agda`
- `DASHI/Cognition/PNF/ExactlyOnceParserAuthorityProjectionExact.agda`
- `DASHI/Cognition/PNF/DeltaNativePNFDreamFlowExact.agda`
- `DASHI/Cognition/PNF/FibreSolverDeltaStreamExact.agda`
- `DASHI/Cognition/PNF/DirectDeltaCompilerArchitectureExact.agda`
- `DASHI/Cognition/PNF/DirectDeltaCompilerActivationExact.agda`
- `DASHI/Cognition/PNF/DirectStreamingRoadmapSynthesisExact.agda`

The semantic prefix/suffix theorem is unchanged by every physical experiment on
this page.

## Exactly-once authority law

Physical parser observation is not semantic authority. Structural partitions,
bilateral context, repairs, retries, and future finer streaming schedules may
observe the same source material, but only one canonical structural owner may
admit it to the semantic fold.

For sentences the current canonical source anchor is the sentence start:

```text
owner_start <= sentence_start < owner_end
    -> structural owner / authority-bearing
otherwise
    -> context observation / evidence-only
```

Boundary-repair partitions are always evidence-only. They may resolve a parser
boundary obligation but do not directly mint sentence, stable-evidence, object,
factor, demand, provenance, or hierarchy authority.

The Python owner is:

- `src/pnf/parser_authority_projection.py`

The DB-free schedule parity owner is:

- `src/pnf/parser_schedule_parity.py`
- `scripts/check_direct_schedule_authority_parity.py`

Schedule parity deliberately reuses `direct_sentence_parity.py`, so physical
schedule parity and G3 direct/reference parity speak the same surrogate-free
object/factor/demand observation language.

## Raw EOF completion and serial floor

For ordered parser partitions with semantic sentence counts `p1..pn`, a fully
serial pipeline can finish all semantic work from `p1..p(n-1)` before parser EOF
on the final partition. Therefore:

```text
serial_eof_floor = sum(p1..p(n-1)) / sum(p1..pn)
overlap_gain = max(0, semantic_complete_at_eof - sum(p1..p(n-1)))
```

Do not cite raw EOF completion without the serial floor and overlap gain.

## Experiment A: coarse partitions, pipe batch 4

The first fresh overlapped workload had sentence counts:

```text
168, 73, 5, 1
```

with about 6 microseconds of active parser/semantic overlap. Raw EOF completion
was 246/247, exactly equal to the serial floor, so overlap completion gain was
zero.

## Experiment B: same partitions, pipe batch 1

Keeping ownership fixed while using `pipe_batch_size=1` produced real active
overlap:

```text
parser/semantic active overlap  ~= 1.938 s
post-parser tail                ~= 6.240 s
direct total                    ~= 27.159 s
spaCy active work               ~= 4.036 s
overlap completion gain          = 0 sentences
```

This proved that the producer/consumer implementation genuinely overlaps, but
the extra parser cost cancelled the concurrency benefit. Experiment B is closed.

## Experiment C: rejected before performance interpretation

The ~12-partition refinement was semantically invalid. The planner predicted 13
structural partitions, but live repair work produced 22 physical partitions and
changed authority-bearing output:

```text
sentences          247 -> 248
tokens/evidence  12750 -> 13177
PNF objects         147 -> 151
PNF factors          69 -> 71
PNF demands         183 -> 188
```

Physical parser-context work also rose to roughly 3.03x source and active overlap
rose to roughly 3.406 s, but **none of those timing numbers are optimization
evidence** because authority parity failed.

This failure exposed the missing global law now implemented by
`ExactlyOnceParserAuthorityProjectionExact.agda` and
`parser_authority_projection.py`.

## Mandatory preflight before any future schedule timing

Before a candidate partition/repair/streaming schedule is eligible for Gate-A
performance interpretation, run the DB-free authority check:

```bash
python scripts/check_direct_schedule_authority_parity.py \
  --text-file README.md \
  --coarse-target-chars 32768 \
  --candidate-target-partitions 12 \
  --context-chars 2048
```

The check parses both schedules, projects observations through exactly-once
ownership, converts each owned sentence through the existing direct compiler,
erases local/database surrogates using the G3 stable parity language, and fails
closed unless the ordered final observations are identical.

Only after this preflight passes may a candidate schedule be benchmarked.

## Current runtime repair

The direct packed-fibre path now enforces:

```text
structural start-anchor owner -> packed sentence -> direct compiler -> PNF
structural context            -> observation only
boundary repair               -> observation only -> obligation resolution
```

Stable token evidence identity is source-coordinate based and no longer includes
a physical partition-local token ordinal in its digest. The ordinal remains a
local packed execution address only.

## Decision rule from here

```text
schedule parity fails
    -> repair ownership/parser-observation projection; do not read timing

schedule parity passes, overlap/tail improve net of parser/context work
    -> keep the physical schedule

schedule parity passes but completed-partition overlap remains uneconomic
    -> stop partition tuning and expose an earlier stable parser prefix/event carrier
```

Do not respond to another schedule-parity failure with downstream one-off fixes.
Repair the exactly-once observation-to-authority projection instead.

No benchmark threshold changes production authority. Bounded G3 direct/reference
parity remains the production cutover gate.
