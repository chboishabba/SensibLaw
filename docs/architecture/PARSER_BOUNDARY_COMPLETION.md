# Parser boundary completion

Status: normative companion to `STREAMING_SEMANTIC_PACMAN.md` and
`STREAMING_OVERLAP_EVIDENCE.md`.

## Formal owners

Before changing this path, inspect the current `dashi_agda` owners:

- `DASHI/Cognition/PNF/ExactlyOnceParserAuthorityProjectionExact.agda`
- `DASHI/Cognition/PNF/ParserBoundaryCompletionExact.agda`
- `DASHI/Cognition/PNF/StreamingSemanticPacmanKernelExact.agda`
- `DASHI/Cognition/PNF/StreamingPhysicalPartitionRefinementExact.agda`

The governing distinction is:

```text
authority owner != evidence supplier
```

Sentence authority is selected exactly once by the canonical sentence-start
anchor. A context or boundary-repair observation may supply a more complete
parser view, but it never becomes another semantic owner.

## Completion law

A structural observation that reaches the right edge of its parser context while
its sentence extends beyond the structural owner is provisional:

```text
start-owned + touches parser context edge
    -> keep owner
    -> open boundary completion obligation
    -> do not publish truncated PNF authority
```

The repair path widens parser context geometrically. When it observes a complete
sentence, that observation is projected back through the original structural
owner coordinates and enters the existing packed-fibre/direct compiler path.

```text
structural owner
      ^
      | authority remains here
      |
repair/context evidence -> completed observation -> existing PNF compiler
```

A physical repair partition never recursively opens another repair and never
owns a second sentence/evidence/PNF identity.

Runtime owners:

- `src/pnf/packed_sentence_fibre.py`
- `src/pnf/parser_authority_projection.py`
- `src/storage/postgres/direct_boundary_completion.py`
- `src/storage/postgres/direct_partition_projection.py`
- `src/runtime/parser_schedule_parity_preflight.py`

## Performance admissibility

Partition timing is inadmissible until the DB-free schedule preflight proves
coarse and candidate schedules have the same stable G3 consumer observation.
The preflight itself performs the same boundary-completion operation in memory.

Only after that equality passes may Gate-A touch PostgreSQL and report timing.

## Diagnostic handoff

`scripts/run_direct_gate_a_benchmark.py` now writes diagnostics into the supplied
`--artifact-root` and automatically creates a sibling archive:

```text
<artifact-root>/receipt-v2.json      # success
<artifact-root>/failure-v2.json      # failure
<artifact-root>.tar.xz               # whole folder, always
```

The tarball includes the ordinary source/cache/timing artifacts already written
under the run folder. Prefer sharing the single `.tar.xz` for debugging or
benchmark review.

## Forbidden shortcuts

Do not:

- publish a sentence that is known only through a truncated context-edge parse;
- grant boundary repair its own semantic authority;
- mint new evidence identity from repair/partition identity;
- compare performance before schedule authority parity;
- add another PNF compiler for completed repairs.
