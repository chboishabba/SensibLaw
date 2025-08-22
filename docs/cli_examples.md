# CLI Usage Examples

## Fetch sections from AustLII

Download specific sections from an Act hosted on AustLII and store them in the
local database:

```bash
sensiblaw austlii-fetch --act https://example.org/act --sections s5,s223
```

## View a stored section

Display the text, extracted rules, provenance and ontology tags for a stored
section identified by its canonical ID:

```bash
sensiblaw view --id s5
```

Both commands use `data/store.db` by default. Provide `--db` to specify a
custom database path.
