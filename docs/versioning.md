# Document Versioning

SensibLaw stores documents in a SQLite database with [FTS5](https://www.sqlite.org/fts5.html)
full‑text search.  Each document receives a unique ID and may have multiple
revisions.  Revisions are timestamped so the database can answer "as‑at"
queries.

## Schema

- `documents` – identity table used to generate IDs.
- `revisions` – holds each revision with its effective date, metadata and body.
- `revisions_fts` – FTS5 index over revision text and metadata for search.

Each revision also records provenance fields:

- `source_url` – where the document was downloaded from.
- `retrieved_at` – timestamp when it was fetched.
- `checksum` – optional hash of the retrieved content.
- `licence` – the licence governing the text.

## Snapshots

Use the `snapshot(doc_id, as_at)` method to retrieve the version of a document
in effect on a given date.  The CLI exposes this via:

```bash
sensiblaw get --id 1 --as-at 2023-01-01
```

The returned JSON includes the provenance metadata captured for the selected
revision.

## Diffs

The store also provides `diff(doc_id, rev_a, rev_b)` which returns a unified
text diff between two revisions of the same document.
