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

The 2026-08-19 strict 0008 profile spent dominant sampled wall time in PostgreSQL
while Python waited in `psycopg.execute()`. The stack was:

```text
materialize_numeric_document_hierarchy()
→ _close_parent_interface()
→ PostgreSQL
```

The lookup close grouped child lookup rows and relied on migration 054's
per-insert export-admission trigger to reject rows whose `(target_kind,target_id)`
was not present in the already-built parent export.

### Corrected production-child diagnosis

The source relation is **not** a global history scan and the earlier
`358,965 -> 125,933 -> 42,836` account is not production evidence. A later
read-only reconstruction followed the actual direct-parent relation and falsified
that traversal.

Authoritative retained-run receipt:

```text
38 parent closes
366,102 direct-child lookup rows
286,904 parent-admitted/stored lookup rows
hottest close = 33.3% of direct-child work
top 10 closes = 82.1%
```

The document parent had three direct adaptive children:

```text
122,034 direct-child lookup rows
 42,836 admitted/stored parent lookup rows
```

The current and pushdown SELECT plans read the same child lookup relation. The
candidate adds an export semi-join; its benefit is therefore not a base-read
reduction. Its physical hypothesis is narrower:

```text
avoid lookup rows which would otherwise be attempted as INSERTs
and rejected by migration-054 admission checks
```

The disposable-clone full INSERT benchmark established exact parity in all 30
alternating trials and reduced the document-root median from 89.35 s to 21.72 s
(75.7%). That result licenses the local rewrite; it does not establish the whole
compiler's parser-relative acceptance target.

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

Measure full INSERT/trigger behavior. A SELECT-only plan is insufficient when the
claimed saving is rejected writes or trigger calls rather than source-row reads.

### Required evidence

- exact parent lookup parity with zero missing/excess rows;
- admission shown to factor through the quotient/grouping key;
- fibre-local rank semantics unchanged;
- parent export/digest/cardinality authority unchanged;
- alternating full-path trials on disposable state;
- separate `N_scan`, `N_admit`, `N_group`, `N_output`, `N_attempt`, `N_commit`;
- trigger calls/time, buffers/WAL where available;
- full strict integration only after the microbenchmark passes.

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

## 14. Delete/rebuild churn on a current projection

### Observed pressure

A fresh strict diagnostic run reported millions of physical PostgreSQL mutations,
including roughly 1.6 million deletes. That aggregate is evidence of a new
optimization frontier, not yet evidence that any particular delete is redundant.

### Smell

```text
identify affected owner/fibre
→ DELETE current projection for that scope
→ recompute/reinsert most or all of the same projection
```

repeated during a cold build or small incremental change.

### Preferred replacement

Only after an owner/parity audit, replace whole-fibre rebuild with the exact
smallest update:

```text
old fibre + Δ producer evidence
→ exact changed keys
→ insert/update/delete only changed rows
```

If a full rebuild is semantically required, retain it and optimize the physical
carrier instead. Delete count alone does not authorize delta maintenance.

### Required evidence

- mutation counts attributed by table/carrier;
- owner/rebuild SQL identified;
- exact before/after projection equality;
- no stale-row survivor under deletion narrowing;
- lower `A_churn` and wall/query work on controlled state;
- no new authority or second current-state projection.

`src/storage/postgres/runtime_churn_audit.py` supplies the read-only attribution
surface. Its cumulative counters are one-run evidence only on a fresh/dedicated
database or with explicit before/after statistics snapshots.

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
inserts / updates / deletes
live rows / dead rows
A_churn
buffer_hits / reads
WAL records / bytes
wall_ns
C_1 / C_10 concentration
```

The old broad history/write ratios remain useful compatibility diagnostics, but
new relational work should keep scan, admission, quotient/grouping, writes and
mutation churn separate. A large `ON CONFLICT DO NOTHING` operation is not cheap
merely because final cardinality changes little.
