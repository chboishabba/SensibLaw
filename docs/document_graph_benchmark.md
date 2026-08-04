# One-document execution benchmark

Use `scripts/benchmark_document_graph_execution.py` to decide whether bounded
parallel execution should be accepted for a representative document.

The harness runs the same canonical input in isolated Python processes with a
serial worker budget and a bounded parallel worker budget. It compares selected
authoritative semantic artefacts after removing only execution receipts.

## Documents 0007 and 0008

```bash
uv run python scripts/benchmark_document_graph_execution.py \
  /path/to/0007_8f26f7a3691b.txt \
  --serial-workers 1 \
  --parallel-workers 4 \
  --repeats 3 \
  --output /tmp/0007-document-graph-benchmark.json

uv run python scripts/benchmark_document_graph_execution.py \
  /path/to/0008.txt \
  --serial-workers 1 \
  --parallel-workers 4 \
  --repeats 3 \
  --output /tmp/0008-document-graph-benchmark.json
```

Each worker-budget run starts in a separate process. Parser/model startup is
therefore charged consistently to both modes, and process-pool startup and owner
merge costs remain part of the parallel document latency.

## Receipt

The output records:

- isolated elapsed-time samples and medians;
- total speedup and milliseconds saved;
- the semantic timing ledger from the representative median run;
- mention and relational-projection process receipts;
- mention, relation, factor, constraint and demand counts;
- authoritative semantic fingerprints;
- semantic parity and latency acceptance results.

The parallel path is accepted only when:

```text
serial semantic fingerprint == parallel semantic fingerprint
and parallel median document latency < serial median document latency
```

A parallel operator receipt must also contain actual worker-process evidence.
`partition_count > 1` without observed worker processes is not accepted as
parallel execution.

## Interpretation

The benchmark answers whether the current implementation improves the complete
document path. A stage-level speedup does not override a slower document result.

If semantic parity fails, the parallel path is invalid regardless of speed. If
parity holds but the parallel path is slower, retain the receipt and adjust the
partition threshold, work granularity or merge strategy rather than forcing the
parallel route.

The output has execution-benchmark authority only. It does not promote semantic
claims or alter the compiled document.
