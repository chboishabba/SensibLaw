# SensibLaw [![CI](https://github.com/OWNER/SensibLaw/actions/workflows/ci.yml/badge.svg)](https://github.com/OWNER/SensibLaw/actions/workflows/ci.yml)

Like coleslaw, it just makes sense.

## Installation

Install the project and its development dependencies:

```bash
pip install -e .[dev]
```

## Testing

Run the test suite:

```bash
pytest
```

## Linting and type checks

Execute all linting and type-check hooks:

```bash
pre-commit run --all-files
```

## CLI

Retrieve a document revision as it existed on a given date:

```bash
sensiblaw get --id 1 --as-at 2023-01-01
```

See [docs/versioning.md](docs/versioning.md) for details on the versioned
storage layer and available provenance metadata.
