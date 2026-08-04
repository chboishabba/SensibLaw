# Post-run progress plots

SensibLaw already retains structured `ProgressEvent` rows in the completed
`PhaseRecorder` ledger.  Plotting uses that ledger directly; it does not create a
second live log, an NPZ archive, a SQLite/Parquet sidecar, or PostgreSQL diagnostic
tables.

For a completed tranche phase:

```bash
uv run python scripts/plot_progress_metrics.py \
  /tmp/sensiblaw-tranche-out/gwb/local_pnf_compile_progress.json
```

By default, output is written beside the ledger in:

```text
local_pnf_compile_progress_plots/
```

The directory contains:

- separate rate graphs by document, stage, and semantic unit;
- a document-stage timeline;
- PNG and SVG versions;
- `progress_plot_manifest.json`, which lists the source event count and generated
  visual artefacts.

For example, parser-projection metrics measured in `sentences/s` are kept on a
separate graph from metrics measured in `tokens/s`, `relations/s`, or `lookups/s`.
This avoids visually meaningless mixed-unit axes.

To request only PNG output or select another destination:

```bash
uv run python scripts/plot_progress_metrics.py \
  /tmp/sensiblaw-tranche-out/gwb/local_pnf_compile_progress.json \
  --format png \
  --output-dir /tmp/sensiblaw-progress-plots/gwb
```

The plots are diagnostic projections only. PostgreSQL remains the semantic
persistence authority, and the human-readable console log remains an execution
surface rather than the plotting source.

## Current scope

The standard one-document-owner tranche path retains outer and child-stage events
in the same recorder, so its completed ledger contains parser, mention,
projection, proposal, fixed-point, and persistence measurements as those stages
emit them.

When `document_workers > 1`, document workers currently own separate process-local
recorders. Merging those child ledgers into the parent run ledger is a separate
execution-transport improvement; the plotter intentionally does not parse the
human log to reconstruct missing process-local events.
