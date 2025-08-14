# Contributing

Contributions to SensibLaw are welcome. To get started, install the development
dependencies and run the test suite:

```bash
pip install -e .[dev,test]
pytest
```

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
