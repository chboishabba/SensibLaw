# SensibLaw
Like coleslaw, it just makes sense.

## CLI

Retrieve a document revision as it existed on a given date:

```bash
sensiblaw get --id 1 --as-at 2023-01-01
```

See [docs/versioning.md](docs/versioning.md) for details on the versioned
storage layer and available provenance metadata.

## Development

Optionally install [pre-commit](https://pre-commit.com/) to run linters and
type checks before each commit:

```bash
pip install pre-commit
pre-commit install
```

The configured hooks will run `ruff`, `black --check`, and `mypy` over the
project's source code.
