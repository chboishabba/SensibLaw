# CI acceptance suite

The CI workflow runs a small acceptance suite after unit tests to ensure
that command-line entry points are wired correctly.

Install the test extras before running the suite:

```bash
pip install -e .[test]
```

The following commands are executed:

```bash
pytest -q
pytest -q -m redflag
python -m src.cli --help
python scripts/generate_sample_corpus.py
python examples/distinguish_glj/demo.py
python -m src.pdf_ingest --help
```

These smoke checks confirm that the main `sensiblaw` interface, sample corpus
generator, demonstration script, and PDF ingestion utility start up without
errors. Contributors adding new CLI entry points should extend both this list
and the CI workflow so the commands are exercised. Red-flag tests enforce the no-reasoning contract and must remain green.
