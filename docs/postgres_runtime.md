# PostgreSQL runtime map

This is the operator-facing source of truth for local PostgreSQL selection.
Several local clusters may exist at once; a running PostgreSQL server is not
automatically the canonical SensibLaw runtime.

## Authority rule

The authority is the active generic schema and its applied migrations:

```text
database/postgres_migrations/
  -> corpus, language, algebra, pnf, evidence, resolution, execution, ...
```

The active semantic rows are in the generic schemas, especially `corpus`,
`algebra`, and `resolution`. The legacy `public.compiler_*` tables are not the
authority for the current compiler runtime.

Select an endpoint explicitly with `DATABASE_URL` or `--database-url`. Do not
infer the target from the presence of a local PostgreSQL process or from the
default port.

## Local cluster matrix

| Role | Endpoint | Data directory | Status | Use |
| --- | --- | --- | --- | --- |
| Previous full tranche run | `postgresql://postgres@127.0.0.1:5433/sensiblaw_tranche` | `/tmp/sensiblaw-pgdata` | disposable test cluster; currently running | Reproduce or inspect the 2026-07-25 `ALL` run |
| Persistent local cluster | socket `/home/c/.local/share/sensiblaw/postgres-18/socket`, port `55432`, database `sensiblaw` | `/home/c/.local/share/sensiblaw/postgres-18` | persistent development cluster | Not the current generic corpus target until its migrations are applied and verified |
| Debug cluster | `postgresql://c@127.0.0.1:55434/sensiblaw` | `/tmp/sensiblaw-pg-debug2.*` | temporary debug instance | Debugging only; never use for an acceptance run |
| Other test cluster | port `55924` | `/tmp/sensiblaw-tranche-*/pgdata` | temporary test instance | Test isolation only |

The 5433 cluster is the database used by the last complete tranche command;
it is not a durable canonical store because its data directory is under
`/tmp`. A new run must either deliberately target it for reproduction or
choose a persistent cluster and first verify the active schemas and applied
migrations.

## Last full run

The command recorded in the shell history was:

```bash
export DATABASE_URL='postgresql://postgres@localhost:5433/sensiblaw_tranche'
python scripts/run_complete_tranche.py \
  --tranche ALL \
  --output-root /tmp/sensiblaw-tranche-out
```

Its output directory was `/tmp/sensiblaw-tranche-out`. It produced GWB source
projection artifacts and PostgreSQL semantic rows, but did not produce a
checkpoint file. The run later hit a foreign-key failure while persisting a
resolution refinement; see `/tmp/sensiblaw-pgdata/server.log`.

## Verify before a run

From `SensibLaw/`, verify the selected target before compiling:

```bash
export DATABASE_URL='postgresql://postgres@127.0.0.1:5433/sensiblaw_tranche'
psql "$DATABASE_URL" -c \
  "select current_database(), current_user;"

psql "$DATABASE_URL" -c \
  "select table_schema, count(*) from information_schema.tables
   where table_schema in ('corpus','algebra','resolution')
   group by table_schema order by table_schema;"
```

For a new persistent target, apply migrations first and confirm that
`corpus.document_occurrence`, `algebra.factor`, `algebra.factor_revision`, and
`resolution.demand` exist before running a tranche. Record the endpoint,
database, data directory, tranche, and output root in the run log.

Never use `rm -rf` against the persistent data directory. The 5433 cluster is
disposable only because the prior setup intentionally created it under
`/tmp`; that does not make other clusters interchangeable.

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
