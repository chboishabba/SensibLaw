# Optimisation Economy

SensibLaw now reviews optimisation on two orthogonal fronts:

1. **runtime economy** — wall time, semantic work, memory, I/O, history-read
   amplification, write amplification, and reuse;
2. **change economy** — how many genuinely new semantic/execution degrees of
   freedom a feature introduces versus how much existing generic capability it
   composes.

Raw LOC is useful context but is not an authority metric. A small helper which
creates a second identity authority is worse architecture than a larger generic
adapter which removes three duplicate lanes.

The executable receipt surface is `src/runtime/optimization_economy.py`. The
known physical anti-patterns are catalogued in `PERFORMANCE_SIN_BIN.md`.

## Runtime economy

For one operation, record conceptually:

```text
E_runtime = (T, W, M, IO, H_read, A_write, R_reuse)
```

where:

- `T` = measured wall/kernel time;
- `W` = semantic work units;
- `M` = peak memory;
- `IO` = explicit I/O units when available;
- `H_read` = historical rows examined / touched semantic rows;
- `A_write` = attempted writes / semantically new writes;
- `R_reuse` = reused work / (reused work + new work).

A missing denominator is `unknown`, not evidence of a finite ratio.

The existing parser-relative target remains separate:

```text
T_post-parser / T_spaCy <= 0.10
```

and may be claimed only from explicit parser/post-parser timing evidence.

## Architecture/change economy

For a feature or optimisation tranche record:

```text
E_architecture =
  (new primitives,
   new semantic authority surfaces,
   new execution engines,
   new persistent schemas/carriers,
   duplicated capabilities,
   reused generic capabilities,
   retired compatibility surfaces)
```

The quantity we are trying to minimise is approximately **new semantic degrees
of freedom introduced per capability**, not lines of source.

A mature feature should increasingly resemble:

```text
existing carrier
+ existing projection
+ existing scheduler/reopening contract
+ existing receipt/persistence boundary
+ small irreducible domain map
```

rather than a lane-local compiler or second authority stack.

## Novelty burden

`ArchitectureEconomy.novelty_burden()` provides a deliberately review-oriented
weighted signal. Its defaults make new authority surfaces and new execution
engines substantially more expensive than a reusable primitive, and make
explicit duplicated capability most expensive.

The score is not a theorem and should not be optimized mechanically. Its purpose
is to make architectural cost visible during review.

The accompanying reuse ratio is:

```text
reused generic capabilities / (reused generic capabilities + new primitives)
```

Again, it is a signal, not permission to hide a necessary new primitive.

## Pareto rule

Performance claims require a common semantic parity/admissibility boundary first.
Only then compare the physical/architecture vectors.

A true Pareto optimisation means:

```text
no runtime cost coordinate worsens
no architecture cost coordinate worsens
retired compatibility surfaces do not decrease
and at least one coordinate strictly improves
```

Typical highest-alpha changes are therefore simultaneously:

```text
faster
+ less history amplification
+ fewer duplicate execution paths
+ more compatibility code retired
```

A speedup purchased by introducing a second semantic authority or execution
engine is a **tradeoff**, not a Pareto win, until that new authority is justified
independently.

## History and write amplification

For an incremental operation define:

```text
H_read  = rows examined from previously materialized state
          / touched or new semantic rows

A_write = rows attempted for insert/update
          / rows that are semantically new
```

These expose costs that wall time alone can hide. A query may finish quickly on a
small fixture while already having the wrong scaling shape.

The desired local-closure law is not literally `H_read = 1`; it is that history
exposure is bounded by the real touched dependency neighbourhood rather than the
entire accumulated carrier.

## Current hierarchy-close specimen

The 2026-08-19 0008 sampling run established a concrete PostgreSQL-dominated
kernel:

```text
materialize_numeric_document_hierarchy()
→ _close_parent_interface()
→ INSERT ... SELECT from semantic_pnf_interface_lookup
   WHERE interface_id = ANY(child ids)
   GROUP BY ...
   ON CONFLICT DO NOTHING
```

Python was predominantly waiting in `psycopg.execute()`. The database session was
active, not lock-blocked. This means further Python/spaCy profiling is not the
right immediate optimisation loop for this kernel.

The structural question is now:

```text
why rediscover child lookup fibres from the accumulated lookup table
if the parent-close producer can consume the bounded child fibres directly?
```

The target shape is:

```text
union(child lookup fibres)
→ bounded canonical parent fibre
→ parent lookup publication
```

with exact parent lookup/export/rank parity.

## Profiling workflow

A full 0008 acceptance run is now an integration proof and hotspot finder, not the
primary micro-optimisation loop.

Use:

```text
full run
→ identify dominant kernel with sampling + database activity
→ extract representative state
→ EXPLAIN / microbenchmark the kernel
→ optimise the equivalent representation
→ prove parity
→ reintegrate
→ rerun full acceptance occasionally
```

For a database hotspot capture where possible:

```text
child/interface IDs supplied
matching source rows
rows scanned
rows grouped
rows attempted
rows actually inserted
conflict count
buffer hits / reads
execution time
hierarchy depth/level
```

Then emit an `AmplificationReceipt` and compare before/after under the same
semantic parity reference.

## Convergence target

A healthy maturing system should trend toward both:

```text
less runtime work per equivalent semantic operation
```

and

```text
less novel implementation machinery per new capability
```

This is a stronger convergence criterion than raw LOC reduction. The best new
features are recombinations of existing proof-bearing carriers and execution
contracts, with only irreducible domain-specific novelty added.
