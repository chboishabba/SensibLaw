# Document Versioning

SensibLaw stores documents in a SQLite database with [FTS5](https://www.sqlite.org/fts5.html)
full‑text search.  Each document receives a unique ID and may have multiple
revisions.  Revisions are timestamped so the database can answer "as‑at"
queries.

## Schema

- `documents` – identity table used to generate IDs.
- `revisions` – holds each revision with its effective date, metadata and body.
- `revisions.document_json` – JSON column containing the full
  [`Document`](../src/models/document.py) structure, including nested
  [`Provision`](../src/models/provision.py) entries and their atoms.
- `provision_text_fts` – FTS5 index over provision text extracted from structured rows.
- `rule_atom_text_fts` – FTS5 index over structured rule atom text.

Each revision also records provenance fields:

- `source_url` – where the document was downloaded from.
- `retrieved_at` – timestamp when it was fetched.
- `checksum` – optional hash of the retrieved content.
- `licence` – the licence governing the text.

## Writing revisions

`VersionedStore.add_revision` serialises the entire `Document` instance into
`document_json`.  Consumers can therefore rely on snapshots reflecting the
structured metadata, provision hierarchy, and extracted atoms produced at
ingest time.

## Snapshots

Use the `snapshot(doc_id, as_at)` method to retrieve the version of a document
in effect on a given date.  The CLI exposes this via:

```bash
sensiblaw get --id 1 --as-at 2023-01-01
```

The returned JSON includes the provenance metadata captured for the selected
revision and the full [`Document`](../src/models/document.py) payload stored in
`document_json`.  Consumers should expect the same schema as defined in the
data models, with provision and atom structures matching
[`Provision`](../src/models/provision.py).

## Diffs

The store also provides `diff(doc_id, rev_a, rev_b)` which returns a unified
text diff between two revisions of the same document.
