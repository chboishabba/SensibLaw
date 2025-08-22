# Contributing

Contributions to SensibLaw are welcome. For a high-level roadmap linking tools
to implementation areas, see [todo.md](todo.md). To get started, install the
development dependencies and run the test suite:

```bash
pip install -e .[dev,test]
pytest
```

The test extras install [Hypothesis](https://hypothesis.readthedocs.io/) for property-based testing.

## Writing tests

New features and fixes should include tests. A helper script is available to
scaffold test files:

```bash
python scripts/gen_test.py src/path/to/module.py
```

This command creates a file such as `tests/path/to/test_module.py` with basic
`pytest` fixtures and a skipped placeholder test. Fill out the TODOs and remove
the `@pytest.mark.skip` decorator once real tests are in place.

Thank you for helping increase the project's test coverage!
