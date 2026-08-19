# Strict Acceptance Attribution

The hierarchy pushdown result moved the optimization frontier.  Exact parity and
a local SQL speedup are not sufficient to establish the production performance
constitution.  A strict run is a parser-relative performance acceptance only when
it contains direct evidence for both sides of:

```text
T_post-spaCy / T_spaCy <= 0.10
```

`LOCAL_PNF_COMPILATION` wall time is not either side of that ratio.

## Existing timing authority

`streaming_spacy_execution.py` already measures monotonic parser/post-parser
occupancy and retains overlap explicitly.  It also measures named post-parser
kernels:

```text
numeric projection worker work
sentence closure worker work
sentence closure coordinator
sentence adjacency
hierarchy materialisation
paragraph adjacency
lookup publication
numeric summary
unclassified orchestration wall
```

`numeric_pnf_compilation.py` now forwards all of those fields into
`numeric_execution_timing` and the completed progress details.  No timing is
reconstructed from total wall time.

`src/runtime/accepted_metric_ledger.py` is the normalized acceptance surface.
Missing occupancy evidence yields:

```text
performance_gate = unknown
accepted_performance = false
```

even when semantic completion and parity pass.

`src/runtime/performance_constitution.py` therefore exposes separate:

```text
semantic_gate
performance_gate
accepted_performance
```

The compatibility `hard_gate` remains the semantic/runtime-completion gate; it is
not a performance claim.

## PostgreSQL churn attribution

The diagnostic fresh run exposed millions of physical mutations.  The next
optimization question is therefore not a PostgreSQL configuration question by
default.  First determine which semantic carrier owns the mutations.

`src/storage/postgres/runtime_churn_audit.py` reads PostgreSQL cumulative counters
without resetting or mutating them.  For each execution/resolution table it
records:

```text
inserts
updates
deletes
live rows
dead rows
sequential scans
index scans
```

and computes:

```text
A_churn = (inserts + updates + deletes) / live rows
```

A positive numerator with zero live rows is `unknown`, not an infinite/finite
claim manufactured by the tool.

These counters are cumulative since PostgreSQL statistics reset.  They provide
one-run attribution only on a fresh/dedicated database or when an explicit
before/after snapshot is available.

## Query-template attribution

If `pg_stat_statements` is already installed, the same audit also reports the
highest cumulative-time execution/resolution templates with calls, rows, buffer
counts, temporary blocks and WAL fields supported by the installed PostgreSQL
version.

The extension is optional.  The audit does not install it, modify
`shared_preload_libraries`, reset its counters or change PostgreSQL settings.

Runtime semantic phase ownership comes from the direct numeric timing ledger;
query-template statistics are a complementary physical attribution surface, not
a replacement for it.

## Command for the next fresh strict run

From the repository root:

```bash
uv run python scripts/report_numeric_pnf_runtime_attribution.py \
  --database-url "$DATABASE_URL" \
  --run-receipt /path/to/strict-or-numeric-receipt.json \
  --output .tmp/numeric-runtime-attribution.json
```

The script is root-executable without a separate `PYTHONPATH=.` requirement.

The output contains:

```text
accepted_metric
postgresql_churn
  totals
  tables[]
  pg_stat_statements_available
  query_templates[]
```

## Decision rule

The immediate optimization target is the highest-cost *semantically owned*
physical kernel, not the largest raw table.

Typical interpretations are:

```text
high DELETE + INSERT on one projection
    -> audit delete/rebuild versus exact delta maintenance

very high trigger-driven calls
    -> test set-wise/producer-native projection

high work-queue UPDATE churn
    -> inspect state-transition/scheduler representation

few giant SQL templates
    -> EXPLAIN (ANALYZE, BUFFERS, WAL) on a disposable clone

many cheap calls
    -> reduce round trips / batch on the finite producer fibre
```

Do not tune `shared_buffers`, `work_mem`, WAL budgets or JIT merely because their
default values look small.  Configuration A/B belongs after the algorithmic work
shape is identified, unless profiling directly falsifies that ordering.

## Acceptance sequence

```text
fresh/dedicated database
-> strict run with durable numeric timing
-> runtime-attribution report
-> identify dominant carrier/query shape
-> optimize with semantic parity
-> repeat focused microbenchmark
-> only then repeat strict performance acceptance
```

Parallel cold calibration remains downstream while one PostgreSQL kernel owns the
post-parser budget.
