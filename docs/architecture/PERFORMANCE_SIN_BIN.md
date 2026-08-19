# Performance Sin Bin

This is SensibLaw's evidence-backed catalogue of physical execution shapes that
have already produced disproportionate cost or semantic risk. It is deliberately
narrower than a generic SQL/Python style guide.

An entry belongs here only when we can name a reproduced specimen, explain the
complexity smell, state the legal replacement shape, and state the parity or
correctness evidence required before replacing it.

The governing optimisation rule is now broader than "avoid history scans":

```text
move consumer-known irrelevance as far upstream as an exact semantic
commutation/intertwiner permits
```

This includes delta projection from changed fibres, but also selective restriction
inside a computation that is already perfectly local.

The companion executable scorecard is
`src/runtime/optimization_economy.py`. The broader review rules live in
`SEMANTIC_HOT_PATH_OPTIMISATION_STYLE_GUIDE.md`.

## 1. Late selective admission after expensive quotient/grouping

### Observed specimen

The 2026-08-19 strict 0008 profile spent the dominant observed wall time in
PostgreSQL while Python waited in `psycopg.execute()`. The stack was:

```text
materialize_numeric_document_hierarchy()
→ _close_parent_interface()
→ PostgreSQL
```

The active lookup query had the shape:

```sql
INSERT INTO execution.semantic_pnf_interface_lookup (...)
SELECT parent_interface_id,
       key_kind, key_a, key_b, target_kind, target_id,
       min(rank)
FROM execution.semantic_pnf_interface_lookup
WHERE interface_id = ANY(child_interface_ids)
GROUP BY key_kind, key_a, key_b, target_kind, target_id
ON CONFLICT DO NOTHING;
```

Migration 054 then applies the actual parent-admission rule per inserted lookup:
there must already be a parent export with the same `(target_kind, target_id)`.

### Corrected diagnosis

The source relation is **not** a global history scan. `_close_parent_interface()`
already restricts the read to the bounded child interfaces. The inefficiency is:

```text
local overlapping child fibres
→ expensive quotient/grouping
→ selective parent admission
```

when the parent admission is constant on the lookup grouping fibres and can be
applied first.

The retained serial baseline made the skew concrete:

```text
38 parent closes
846,020 raw child lookup rows
366,102 unrestricted deduplicated child-union rows
286,904 stored parent lookup rows

hottest close = 42.4% of all close lookup reads
top 10 closes = 77.7%
```

For the document root:

```text
raw child rows                358,965
unrestricted grouped union    122,034
parent-admitted raw rows       125,933
stored parent rows              42,836
```

Read-only parity established:

```text
dedup(child lookup fibres) ∩ parent admitted exports
== stored parent lookup
```

with zero missing and zero excess rows.

### Complexity smell

```text
X
→ quotient/fold Q(X)
→ selective consumer restriction R(Q(X))
```

when the consumer/router predicate factors through the quotient key and the fold
is fibre-local.

This is not a blanket rule to "filter early". If admission depends on a hidden
member coordinate, aggregate cardinality, provenance diversity, minimum rank, or
some other quantity changed by the fold, pushdown may be semantically invalid.

### Preferred replacement

When an exact commuting square is established:

```text
R(Q(X)) == Q(R↑(X))
```

use:

```text
bounded child fibres
→ parent-admission semi-join
→ quotient/group/min-rank
→ parent publication
```

For the observed root this reduces rows entering grouping from `358,965` to
`125,933` — 64.9% — while retaining the same `42,836` output rows.

That is a claim about grouping input, **not yet** a claim of 64.9% fewer base rows
read or 64.9% lower wall time. Those require planner/execution evidence.

### Required evidence

Before production replacement:

- exact parent lookup parity with zero missing/excess rows;
- admission shown to factor through the quotient/grouping key;
- fibre-local `min(rank)` semantics unchanged;
- parent export/digest/cardinality authority unchanged;
- `EXPLAIN (ANALYZE, BUFFERS)` before/after on cloned representative state;
- separate `N_scan`, `N_admit`, `N_group`, `N_output`, `N_attempt`, `N_commit`;
- full strict integration after the microbenchmark passes.

The executable candidate/parity probe is
`src/storage/postgres/hierarchy_close_admission_pushdown.py`.

## 2. Relation → row triggers → relation

### Smell

A batch insert decomposes into `FOR EACH ROW` trigger calls, each searching
surrounding state and reconstructing another relation.

### Replacement

Use transition tables / set projection when the derived carrier factorizes over
the inserted or updated relation.

### Existing specimens

Demand constraints, H3 scheduling, sentence-region publication, candidate
lifecycle, evidence wakeup, and several demand projections were converted from
this shape during the owner-hot-path tranche.

## 3. Producer knows coordinate → consumer reconstructs coordinate

### Smell

The producer possesses an exact sentence/token/object/factor coordinate, writes a
weaker carrier, then a downstream query searches the database to recover the
same coordinate.

### Replacement

Flow producer-native coordinates forward, with defensive reconstruction retained
only as a compatibility/fail-closed path. Exactness requires:

```text
direct_projection(P) == reconstruct(materialize(P))
```

under the same uniqueness rules.

## 4. Repeated correlated point lookup instead of one finite summary

### Smell

For each row in a finite producer batch, execute a correlated lookup/count to
establish uniqueness or a reusable classification.

### Replacement

Group the finite support relation once by the real key, retain exactly the
unique cells, then join the producer batch to that summary.

## 5. Hot automatic maintenance of a cold compatibility carrier

### Smell

A historical projection remains updated on every production mutation although
no live production consumer reads it.

### Replacement

After a complete live-consumer and live-obligation audit, move the carrier to an
explicit exact rebuild:

```text
current authority → rebuild legacy observation on request
```

Cold means exactly rebuildable, not approximate.

## 6. Whole-document/corpus scan in an incremental consumer

### Smell

A local edit/evidence atom wakes containment scope because document/corpus scope
is easy to query rather than because every row is semantically dependent.

### Replacement

Use reverse dependency:

```text
Δ source/evidence → affected fibres → bounded consumer frontier
```

Sound over-wake is acceptable when declared; missing required dependencies are
not.

## 7. Repeated text/JSON decoding after numeric parser projection

### Smell

Ordinary post-spaCy semantic execution converts numeric symbols back into text to
make identity, role, or relation decisions that already have numeric authority.

### Replacement

Keep post-parser execution numeric. Text is allowed at defended ingestion,
external protocol, parser adapter, human-facing export/audit, and explicit legacy
identity boundaries.

## 8. Python per-element SQL over a relation already in PostgreSQL

### Smell

Fetch IDs to Python merely to execute one SQL statement per element back into the
same database.

### Replacement

Prefer `INSERT ... SELECT`, `UPDATE ... FROM`, bounded staging, transition tables,
or a producer-native set projection.

## 9. DISTINCT/GROUP BY used downstream to repair multiplicity created upstream

### Smell

An earlier join creates avoidable multiplicity and a later global/grouped
operation is relied on to restore set semantics.

### Replacement

Canonicalize/narrow the finite input before the expensive join. Deduplicate at
the smallest semantically complete carrier.

## 10. Append-only history rescanned to reconstruct current state per operation

### Smell

Authoritative history is repeatedly scanned with latest/distinct logic during
ordinary reads or writes.

### Replacement

Keep append-only authority but maintain a compact exactly rebuildable current
projection only when a live consumer exists.

## 11. Observability that performs semantic-scale work

### Smell

Compilation wall time includes whole-document/corpus counts, quality scans, or
reports whose only consumer is a benchmark receipt.

### Replacement

Treat observability as a consumer. Put expensive scans behind explicit modes and
measure their cost separately.

## 12. Generic fallback semantics running beside a stronger producer-native path

### Smell

The strict producer supplies stronger coordinates but legacy reconstruction or
fallback triggers still execute automatically and may even overwrite producer
state.

### Replacement

Use capability/fence selection so the strict producer owns the direct path and
the fallback remains available only for writers which lack the stronger
contract.

## 13. Unbounded `ANY(...)` / giant `IN (...)` as an accidental batch API

### Smell

A nominally set-wise operation is still unbounded in memory/planner work and may
hide a large relation behind an ID vector.

### Replacement

Use bounded fibres/stages with explicit cardinality, or a relational join whose
scope is indexed and semantically local.

## Review evidence template

Every new sin-bin specimen should record:

```text
antipattern:
observed specimen:
symptom:
detection:
semantic input fibre:
consumer/router:
commutation/factorization obligation:
why it hurts:
legal replacement:
parity/correctness proof required:
before metrics:
after metrics:
```

At minimum record these physical counts when meaningful:

```text
N_scan
N_admit
N_group
N_output
N_attempt
N_commit
buffer_hits / reads
wall_ns
C_1 / C_10 concentration
```

The old broad history/write ratios remain useful compatibility diagnostics, but
new relational work should keep scan, admission, quotient/grouping and writes
separate. A large `ON CONFLICT DO NOTHING` operation is not cheap merely because
final cardinality changes little.
