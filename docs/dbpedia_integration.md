# DBpedia Integration (Thin Slice, No Local Triple Store)

DBpedia is treated as an **external advisory knowledge source**.

We do **not** submodule DBpedia dumps or run a local triple store by default.
Instead, we:

- resolve name -> candidate DBpedia URIs at curation time (Lookup API or SPARQL)
- curate the mappings (reviewable JSON batches)
- upsert them into our DB as `actor_external_refs` / `concept_external_refs`
- export them as `owl:sameAs` / `skos:exactMatch` triples when building graphs

This matches the “DBpedia/Wikitology as global ontology” framing from the canonical
thread `Data management ontology topology` while preserving our authority boundaries.

## What "integration" means in our ontology

DBpedia does not define our WrongTypes/Duties/ProtectedInterests/ValueFrames.

DBpedia integration means:

- **entity resolution**: attach stable external IDs to internal entities
  - actors: hospitals, agencies, organisations, places
  - concepts: general-world concepts we intentionally model internally
- **search + clustering enrichment**: use DBpedia labels/types/categories as weak
  signals (profile-bound), not as semantic truth

## Querying DBpedia (curation time)

Preferred for string->URI:

- `SensibLaw/scripts/dbpedia_lookup_api.py "Westmead Hospital" --max-results 5`

### Generate a curated batch skeleton (recommended)

To reduce copy/paste errors, you can emit a JSON batch skeleton compatible with
`ontology external-refs-upsert`. This keeps DBpedia integration *curation-time*
and audit-friendly:

```bash
SensibLaw/scripts/dbpedia_lookup_api.py "Westmead Hospital" --max-results 5 \
  --emit-batch SensibLaw/.cache_local/external_refs_westmead.json
```

Then open the emitted file and either:

- select a candidate row and fill `actor_id`/`concept_code`, or
- re-run with `--pick N` plus an anchor to emit an actual `actor_external_refs`
  / `concept_external_refs` row.

SPARQL is available but may be slower/flakier:

- `SensibLaw/scripts/dbpedia_lookup.py "westmead hospital" --limit 10 --method get`

Query patterns:

- `docs/dbpedia_queries.md`

## Persisting external refs (our DB)

Curate a JSON batch in the format:

```json
{
  "actor_external_refs": [
    {
      "actor_id": 42,
      "provider": "dbpedia",
      "external_id": "http://dbpedia.org/resource/Westmead_Hospital",
      "external_url": null,
      "notes": "curated; source=lookup; types include dbo:Hospital"
    }
  ]
}
```

Then upsert:

```bash
python -m cli ontology external-refs-upsert --db path/to/sensiblaw.db --file external_refs.json
```

See:
- `docs/ONTOLOGY_EXTERNAL_REFS.md`

## Example: Westmead Hospital

Lookup API yields the candidate URI:

- `http://dbpedia.org/resource/Westmead_Hospital`

and DBpedia ontology types (examples):

- `http://dbpedia.org/ontology/Hospital`
- `http://dbpedia.org/ontology/Place`

Our posture:

- attach the URI to the internal `actors` row (and optionally store type hints in `notes`)
- if we want to use “dbo:Hospital” at all, it becomes a **profile-bound hint** for
  actor classification (`actor_class_id`) or UI grouping, not a canonical definition

## Artifact hygiene

Both lookup scripts cache under `SensibLaw/.cache_local/` which is gitignored.
