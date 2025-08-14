# Goldset Harness

The goldset harness exercises core extractors against a small set of
annotated examples.

## Datasets

Gold set fixtures live under `tests/goldsets/`:

- `sections.json` – HTML snippets with expected cross references.
- `citations.json` – mock Act data with expected citation edges.
- `checklists.json` – story fixtures with expected factor outcomes.

## Usage

Run the evaluation from the repository root:

```bash
sensiblaw eval goldset
```

Use `--threshold` to set the minimum precision/recall (defaults to `0.9`).
The command prints metrics for citations, cross‑references and checklist
factors and exits with a non‑zero status if any metric falls below the
threshold. Continuous integration runs this command to detect
regressions.
