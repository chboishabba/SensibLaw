# Optimisation Economy

SensibLaw now reviews optimisation on two orthogonal fronts:

1. **runtime economy** — wall time, semantic work, memory, I/O, relational
   amplification, and reuse;
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
E_runtime = (T, W, M, IO, relational work, R_reuse)
```

where `T`, `W`, `M`, and `IO` retain their ordinary meanings and
`R_reuse = reused_work / (reused_work + new_work)`.

For relational kernels, do not collapse all database work into one history-read
ratio. Record the cardinality flow:

```text
N_scan       source rows examined
N_admit      rows surviving consumer/admission restriction
N_group      rows entering quotient/group/fold work
N_output     canonical semantic output rows
N_attempt    attempted writes
N_commit     committed/new writes
```

This yields distinct diagnostics:

```text
A_scan      = N_scan / N_output
A_quotient  = N_group / N_output
S_admission = N_admit / N_scan
A_write     = N_attempt / N_commit
```

A reduction in `N_group` is not automatically a reduction in `N_scan`. Predicate
pushdown may save hash/sort/group work while PostgreSQL still reads the same base
rows. Receipts must keep those claims separate.

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

A speedup purchased by introducing a second semantic authority or execution
engine is a **tradeoff**, not a Pareto win, until that new authority is justified
independently.

## Consumer restriction before quotient/fold

The 2026-08-19 retained strict serial baseline corrected an earlier diagnosis.
`_close_parent_interface()` is **already child-local**: it reads only the lookup
and export rows belonging to `child_interface_ids`. It is not a global-history
reconstruction.

The expensive shape is narrower:

```text
local overlapping child lookup rows
→ GROUP BY / min(rank)
→ migration-054 parent-export admission
→ retained parent lookup
```

The parent admission rule depends only on `(target_kind, target_id)`, so for this
consumer it factors through the lookup grouping key. The legal candidate is:

```text
local child lookup rows
→ semi-join to parent admitted exports
→ GROUP BY / min(rank)
→ retained parent lookup
```

The semantic obligation is an exact commuting square, not a generic command to
"filter early":

```text
restrict_parent(group_children(rows))
==
group_children(restrict_child_rows(rows))
```

Admission must select/reject whole grouping fibres and the fold must remain
fibre-local. If two rows share one quotient key but the router admits one and
rejects the other, pushdown is invalid.

This is consumer-indexed relevance: a key excluded from one parent publication is
not thereby globally irrelevant or erasable.

## Retained-baseline forensic evidence

The read-only pass over the completed serial baseline found:

```text
interfaces          25,457
lookup rows         888,856
export rows         503,733
parent closes            38

all closes:
child rows read     846,020
dedup child union   366,102
stored parent rows  286,904
raw/union              2.31x
raw/output             2.95x
```

Work is highly concentrated rather than mean-like:

```text
hottest close share   42.4%
top-10 close share    77.7%
```

The document root is the canonical specimen:

```text
raw child lookup input        358,965
unrestricted grouped union    122,034
parent-admitted raw input      125,933
stored parent lookup output     42,836
```

Read-only extensional comparison established:

```text
dedup(child lookup fibres) ∩ parent admitted exports
== stored parent lookup
```

with zero missing and zero excess rows.

Pushing the existing admission semi-join ahead of grouping would therefore reduce
rows entering the root grouping stage from `358,965` to `125,933`, a measured
**64.9% grouping-input reduction**, while preserving the same `42,836` output
rows. This does not yet prove a 64.9% reduction in base-table reads or wall time;
that is a planner/microbenchmark question.

The executable candidate/parity probe lives in
`src/storage/postgres/hierarchy_close_admission_pushdown.py`.

## Heavy-tail optimisation pressure

Mean operation cost can conceal the real frontier. Record a concentration curve:

```text
C_k = work in k hottest operations / total work
```

When `C_1` or `C_10` is large, optimise the upper strata before spending effort on
uniform micro-improvements. After each successful optimisation, reprofile the
residual rather than assuming the whole stage is solved.

## Profiling workflow

A full 0008 acceptance run is now an integration proof and hotspot finder, not the
primary micro-optimisation loop.

Use:

```text
full run
→ identify dominant kernel with sampling + database activity
→ inspect retained state read-only
→ formulate exact consumer/factorization law
→ run parity audit
→ clone representative state
→ EXPLAIN ANALYZE / microbenchmark old vs candidate
→ optimise only after parity
→ reprofile residual
→ rerun full acceptance occasionally
```

For a database hotspot capture where possible:

```text
N_scan
N_admit
N_group
N_output
N_attempt
N_commit
buffer hits / reads
execution time
hierarchy depth/level
C_1 / C_10 concentration
```

## Convergence target

A healthy maturing system should trend toward both:

```text
less runtime work per equivalent semantic operation
```

and

```text
less novel implementation machinery per new capability
```

The stronger runtime principle is now:

```text
move consumer-known irrelevance as far upstream as an exact semantic
intertwiner permits
```

—not merely "avoid global history scans". The input may already be perfectly
local and still carry quotient fibres that the current consumer has proved it
cannot observe.
