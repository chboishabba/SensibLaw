# Live parser-token INSERT integrity attribution

The strict parser producer now writes complete numeric token/head authority rows on
the first persistent INSERT.  The remaining first-write cost is dominated by
PostgreSQL referential-integrity and index machinery.  This diagnostic measures
that real statement without weakening the schema.

Enable selected process-local token COPY batch ordinals:

```bash
export SENSIBLAW_TOKEN_INSERT_EXPLAIN_ORDINALS=1,16,32
export SENSIBLAW_TOKEN_INSERT_EXPLAIN_OUTPUT="$PWD/.tmp/token-insert-explain.jsonl"
```

Run the ordinary strict serial committed-prefix diagnostic.  Each selected batch
executes the genuine

```text
INSERT INTO execution.semantic_parser_token ...
SELECT ... FROM tmp_parser_token
ON CONFLICT DO NOTHING
```

under `EXPLAIN (ANALYZE, BUFFERS, WAL, VERBOSE, SETTINGS, FORMAT JSON)` inside the
original parser partition transaction.  All active constraints, indexes and
triggers remain enabled.  Internal PostgreSQL RI triggers are included in the
inventory deliberately.

Installation order is part of the contract: this observer wraps `_copy_rows`
before `numeric_parser_projection_hot_path` captures it.  Consequently migration
175 producer-complete enrichment (`sentence_id`, `token_id`, `head_token_id`) is
already present when the observed INSERT executes.

Summarize the capture with:

```bash
uv run python scripts/summarize_live_token_insert_explains.py \
  --input .tmp/token-insert-explain.jsonl \
  --output .tmp/token-insert-explain-summary.json
```

The summary reports per-batch execution/WAL/buffer metrics, exact FK/index counts,
referenced relation counts, and ranked EXPLAIN trigger timings.  It does not
pretend that trigger timing alone decomposes heap/index executor cost; the cgroup
PostgreSQL flame profile remains the independent observer for `ExecInsertIndexTuples`,
B-tree work and RI/SPI stacks.

This is diagnostic evidence only.  It neither constitutes a full performance
acceptance run nor licenses removal/disablement of any foreign key or index.
