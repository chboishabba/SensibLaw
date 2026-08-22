# Genuine live region-close EXPLAIN

The accepted strict serial run at migration 174 established that sentence-region
closure is the dominant PostgreSQL kernel.  A completed database cannot be turned
back into its historical pre-close state by changing only
`semantic_pnf_region.closure_state`: close-trigger projections have already
advanced demand/anaphor/candidate state, and the integrity fences correctly reject
that counterfactual replay.

The diagnostic contract is therefore **capture history at the real transition**,
not reconstruct it afterward.

## Exact method

Set both variables before starting a fresh strict **serial** run:

```bash
export SENSIBLAW_REGION_CLOSE_EXPLAIN_ORDINALS=100,6355,12600
export SENSIBLAW_REGION_CLOSE_EXPLAIN_OUTPUT="$PWD/.tmp/live-region-close-explain.jsonl"
```

When configured, the closure hot-path installer wraps the canonical
`persist_sentence_closure_setwise` before bounded sentence leasing captures it.
For each selected run-scoped sentence-close ordinal, the canonical SQL

```sql
UPDATE execution.semantic_pnf_region
   SET closure_state = ...,
       graph_revision = ...,
       closed_at = CURRENT_TIMESTAMP
 WHERE region_id = ...;
```

is executed as

```sql
EXPLAIN (ANALYZE, BUFFERS, WAL, VERBOSE, SETTINGS, FORMAT JSON)
UPDATE ...;
```

`EXPLAIN ANALYZE` executes the real UPDATE and every attached trigger in the
**original sentence transaction**.  The probe therefore does not:

- reopen a completed region;
- split sentence atomicity;
- commit a partial pre-close state;
- disable or bypass triggers;
- weaken demand/anaphor/candidate integrity;
- create another close implementation.

The selected record additionally contains the exact `pg_trigger` inventory and
`pg_get_functiondef` bodies visible at that schema frontier.

## Ordinal semantics

The close ordinal is stored in an fsynced diagnostic ledger shared by all Python
processes in the run.  This matters even with `--closure-workers 1`: the strict
executor can create replacement processes over the lifetime of one diagnostic.
The prefix wrapper resets that ledger before launch and fails the diagnostic if
the observed record ordinals are not exactly the requested sequence.  The probe
remains serial-only: multiple concurrent closers would make ordinal order a
schedule artefact rather than a stable accumulated-state stratum.

The committed-prefix boundary uses the same run-scoped, fsynced control-plane
discipline.  A replacement worker continues the existing committed-close count;
an attempt to run beyond the requested boundary fails the diagnostic rather than
claiming an inexact prefix.

The suggested `100,6355,12600` positions sample early/middle/late closure for the
12,710-sentence GWB workload.  They test whether close cost grows with accumulated
derived state rather than guessing cheap/median/expensive rows after completion.

## Durability and commit verification

Each selected EXPLAIN record is appended and fsynced after the canonical sentence
persistence function completes, but still before the outer transaction context
commits.  The record therefore says
`commit_confirmation=not_observed_by_in_transaction_probe`.

After the run, verify the persisted fibres read-only:

```bash
uv run python scripts/summarize_live_region_close_explains.py \
  --input .tmp/live-region-close-explain.jsonl \
  --database-url "$DATABASE_URL" \
  --output .tmp/live-region-close-explain-summary.json
```

The verifier checks that each selected region is `LOCALLY_CLOSED` and its exact
work item is `COMPLETED`.  A missing configured ordinal or an unconfirmed commit
is diagnostic failure, not evidence to optimize from.

## Interpretation

The experiment is intended to distinguish at least these cases:

1. approximately constant trigger cost per sentence;
2. cost increasing with accumulated document/derived-state size;
3. one named trigger dominating all strata;
4. changing trigger composition across strata;
5. temporary/WAL/buffer amplification arising inside a specific derived
   projection.

Only after this decomposition should a derived projection be considered for
deferred join/set-wise reconciliation.  Deferral remains consumer/projection
specific: join what is proved idempotent/order-independent; retain explicit braid
obligations where order or provenance remains observable.
