# PostgreSQL runtime map

This is the operator-facing source of truth for SensibLaw's local runtime
selection. The sole supported default target is the dedicated TrueNAS database:

```text
postgresql://admin:<password>@truenas.local:5432/sensiblaw_sparse_ready_20260818
```

Keep the actual password only in the ignored `.env` file. Do not put it in a
shell history entry, report, test output, or tracked file.

## Authority rule

The authority is the active generic schema and its applied migrations:

```text
database/postgres_migrations/
  -> corpus, language, algebra, pnf, evidence, resolution, execution, ...
```

The active semantic rows are in the generic schemas, especially `corpus`,
`algebra`, `resolution`, and `execution`. The legacy `public.compiler_*` tables
are not the authority for the current compiler runtime.

Runtime commands must load the ignored local configuration before invoking a
script. Scripts retain their explicit `--database-url` override.

```bash
set -a
. ./.env
set +a
psql "$DATABASE_URL" -c 'select current_database(), current_user;'
```

## Supported target and preflight

| Role | Endpoint | Status | Use |
| --- | --- | --- | --- |
| SensibLaw runtime | `truenas.local:5432/sensiblaw_sparse_ready_20260818` | migration-145 complete; reserved for measurements | Sole default for strict calibration and production complete-tranche runs |

Before every workload, verify reachability, migration 145, available capacity,
and that the reserved database starts without compilation builds or semantic
runs. The recorded target had 98 GiB free capacity at handover; recheck it, do
not treat that observation as a perpetual guarantee.

```bash
set -a
. ./.env
set +a

psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -c \
  "select current_database(), current_user, pg_size_pretty(pg_database_size(current_database()));"
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -c \
  "select exists (
     select 1 from public.sensiblaw_schema_migration
     where migration_name = '145_sparse_frontier_dirty_closure.sql'
   ) as migration_145_applied;"
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -c \
  "select
     (select count(*) from execution.document_compilation_build) as builds,
     (select count(*) from execution.semantic_pnf_run_identity) as semantic_runs;"
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -c \
  "select pg_size_pretty(sum(pg_tablespace_size(oid))) as visible_tablespace_usage
   from pg_tablespace;"
```

Proceed only when migration 145 is present and both starting counts are zero.
Record the capacity check with the run receipt. The tablespace query reports
visible database usage only; use the TrueNAS storage report as the authoritative
free-space figure.

## Retired local exact-0008 cluster

`/tmp/sensiblaw-pr485-pg.wB1DN7` was a disposable diagnostic cluster, not a
runtime target. Its final `postgres.log` records the failure sequence on
2026-08-18: `/tmp` quota exhaustion prevented extension of
`execution.semantic_parser_token`, WAL temporary-file writing panicked during
autovacuum, and PostgreSQL terminated then shut down during recovery. Preserve
that log as the diagnostic record before removing the data directory. Do not
restart or target this cluster.

Other documentation that mentions `127.0.0.1:5433` is historical evidence
only, not a runnable default. New commands must source `.env` and use the
TrueNAS database.

## Complete-tranche measurement contract

Use fresh output and ledger roots for each strict calibration. Calibration
runs are intentionally rolled back; production runs are not.

```bash
set -a
. ./.env
set +a

uv run python scripts/benchmark_complete_tranche_phases.py \
  --tranche GWB \
  --database-url "$DATABASE_URL" \
  --input-path /absolute/path/to/0008.epub \
  --output-root .tmp/exact-0008-truenas-calibration-serial \
  --ledger-root .tmp/exact-0008-truenas-calibration-serial-ledger \
  --typing-workers 1 --closure-workers 1 --owner-partitions 1 \
  --parser-workers 1 --worker-budget 1 --strict-exact
```

Then run the strict production shape in a separate rolled-back calibration root:
`--worker-budget 4 --closure-workers 4 --owner-partitions 8`. Require
`strict-numeric-postgresql`, zero rollback counts, no failure references,
durable outer phase timings, and resource/stage ledgers from both runs.

After calibration, run one separate strict offline non-calibration complete
tranche against the same database. Invoke the unchanged sparse-frontier
reduction for its run/document references and require a receipt reporting zero
rebuilt frontiers. Rank any compact report by actual phase wall time first, and
include the commit SHA, EPUB digest, migration level, worker shape, peak
RSS/PSS, reduction-scan amplification, reuse/failure counts, and that
frontier-idempotence receipt. Do not claim an hour-scale path until completed
strict runs provide those terminal receipts.

## Document compiler progress contract

Document progress reports named stages for every material CPU-heavy region.
After parser observation projection, the compiler reports local typing and
diagnostics, base proposal generation, streaming closure, PNF graph
construction, constraint assessment/refinement, and resolution-demand
derivation. There should be no long-running work between a completed stage and
the next stage start.

Stage measures are cumulative snapshots of the current kernel and are emitted
periodically from bounded loops where practical. A measure that is only known
at the end is reported as a final total, not interpreted as incremental
throughput. The progress plotter may derive rates only when at least two
changing cumulative samples exist; otherwise it labels the rate unavailable.
