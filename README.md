# SensibLaw
Like coleslaw, it just makes sense.

## Installation

Install the package in editable mode to develop locally:

```bash
pip install -e .
```

## CLI

Retrieve a document revision as it existed on a given date:

```bash
sensiblaw get --id 1 --as-at 2023-01-01
```

See [docs/versioning.md](docs/versioning.md) for details on the versioned
storage layer and available provenance metadata.
