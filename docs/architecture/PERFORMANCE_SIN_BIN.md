# Performance Sin Bin

This is SensibLaw's evidence-backed catalogue of physical execution shapes that
have already produced disproportionate cost or semantic risk. It is deliberately
narrower than a generic SQL/Python style guide.

An entry belongs here only when we can name a reproduced specimen, explain the
complexity smell, state the legal replacement shape, and state the parity or
correctness evidence required before replacing it.

The governing transformation is:

```text
project from the finite changed semantic fibre
rather than rediscovering that fibre from accumulated history
```

The companion executable scorecard is
`src/runtime/optimization_economy.py`. The broader review rules live in
`SEMANTIC_HOT_PATH_OPTIMISATION_STYLE_GUIDE.md`.

## 1. Growing self-read aggregate + conflict upsert

### Observed specimen

The 2026-08-19 strict 0008 profile spent the dominant observed wall time in
PostgreSQL while Python waited in `psycopg.execute()`. The stack was:

```text
materialize_numeric_document_hierarchy()
→ _close_parent_interface()
→ PostgreSQL
```

The active query had the shape:

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

The same parent-close path performs an analogous grouped copy over
`semantic_pnf_interface_export`.

### Complexity smell

```text
growing materialized relation R
→ filter R by child IDs
→ GROUP BY / deduplicate
→ write back into R
→ use ON CONFLICT as final deduplication
```

Repeated while `R` grows, this can make hierarchy closure proportional to
previously materialized state rather than the finite changed child fibre.

### Preferred replacement

```text
bounded child fibres ΔR
→ canonical union/dedup within ΔR
→ one parent projection
→ append only genuinely new parent rows
```

In symbols:

```text
⋃ child c of p: L(c)  →  L(p)
```

rather than rediscovering those child fibres through a global accumulated
lookup table when the producer already owns equivalent bounded child sketches or
rows.

### Required evidence

Before replacement:

- exact parent lookup/export parity;
- ambiguity/rank semantics unchanged;
- parent interface digest/cardinality parity where those fields are authoritative;
- `EXPLAIN (ANALYZE, BUFFERS)` before/after on representative state;
- rows examined/grouped/attempted/inserted;
- history-read amplification and write amplification;
- full strict integration after the microbenchmark passes.

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
hide a whole-history query behind a large ID vector.

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
consumer:
why it hurts:
legal replacement:
parity/correctness proof required:
before metrics:
after metrics:
```

At minimum record these physical counts when meaningful:

```text
N_input
N_touched
N_history_examined
N_grouped
N_write_attempts
N_semantically_new_writes
buffer_hits / reads
wall_ns
```

with the two headline amplification measures:

```text
H_read  = historical rows examined / touched semantic rows
A_write = attempted writes / semantically new writes
```

A large `ON CONFLICT DO NOTHING` operation is not cheap merely because final
cardinality changes little.
