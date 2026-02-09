# External Ontology References

This guide explains how to attach SensibLaw concepts and actors to external ontology identifiers (e.g., Wikidata, DBpedia, YAGO, WordNet) using the `concept_external_refs` and `actor_external_refs` tables. It also shows how to look up candidates, curate a JSON batch, and upsert the links so they appear in the database and downstream graph exports.

## Table overview

- **`concept_external_refs`** stores external IDs against canonical concepts. Each row records the `concept_id`, `provider` (e.g., `wikidata`), `external_id` (such as a Q-ID or DBpedia URI), plus optional `external_url` and free-text `notes`. A `(concept_id, provider, external_id)` tuple is unique to avoid duplicates.【F:database/migrations/002_concept_substrate.sql†L40-L58】
- **`actor_external_refs`** mirrors the pattern for people, organisations, and places with `actor_id`, `provider`, `external_id`, optional `external_url`, and `notes`.【F:database/migrations/002_concept_substrate.sql†L50-L58】

### DBpedia representation (recommended)

For DBpedia, store `external_id` as the **full DBpedia URI**, for example:

- `http://dbpedia.org/resource/Westmead_Hospital`

This ensures downstream graph exports can emit valid `owl:sameAs` / `skos:exactMatch`
targets without inventing a CURIE scheme.

## Running lookups

1. Pick a search template from [`docs/wikidata_queries.md`](./wikidata_queries.md) (for example, the fuzzy merchant query).【F:docs/wikidata_queries.md†L243-L270】
2. Save the SPARQL to a file and execute it against the public endpoint:

   ```bash
   cat > /tmp/wikidata_lookup.sparql <<'SPARQL'
   SELECT ?item ?itemLabel ?countryLabel WHERE {
     ?item rdfs:label|skos:altLabel ?label .
     FILTER (LANG(?label) = "en") .
     FILTER (CONTAINS(LCASE(?label), "woolworths")) .
     OPTIONAL { ?item wdt:P17 ?country . }
     SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
   }
   LIMIT 50
   SPARQL

   curl -H "Accept: application/sparql-results+json" \
     --data-urlencode query@/tmp/wikidata_lookup.sparql \
     https://query.wikidata.org/sparql | jq '.results.bindings'
   ```
3. Select the best `external_id` (e.g., `Q1035965` for Westmead Hospital) and note the human-readable label returned in the bindings.【F:docs/external_ontologies.md†L146-L181】

### DBpedia (Lookup API; curation time)

For DBpedia, prefer the Lookup API helper (lighter weight than SPARQL):

```bash
SensibLaw/scripts/dbpedia_lookup_api.py "Westmead Hospital" --max-results 5
```

To emit a curated batch skeleton compatible with `ontology external-refs-upsert`:

```bash
SensibLaw/scripts/dbpedia_lookup_api.py "Westmead Hospital" --max-results 5 \
  --emit-batch SensibLaw/.cache_local/external_refs_westmead.json
```

This produces a reviewable JSON file you can edit into the `actor_external_refs`
/ `concept_external_refs` payload format below.

## JSON batch format

Curate lookups into a single JSON payload that separates concept and actor inserts. The `concept_code` is resolved to `concept_id` during upsert, while actor rows use the primary key you already have in your database.

```json
{
  "concept_external_refs": [
    {
      "concept_code": "HOUSING_RENT",
      "provider": "wikidata",
      "external_id": "Q167384",
      "external_url": null,
      "notes": "optional curator notes"
    }
  ],
  "actor_external_refs": [
    {
      "actor_id": 42,
      "provider": "wikidata",
      "external_id": "Q1035965",
      "external_url": null,
      "notes": "optional curator notes"
    }
  ]
}
```

For DBpedia, the same structure applies; just use `provider: "dbpedia"` and a full
URI `external_id`:

```json
{
  "actor_external_refs": [
    {
      "actor_id": 42,
      "provider": "dbpedia",
      "external_id": "http://dbpedia.org/resource/Westmead_Hospital",
      "external_url": null,
      "notes": "optional curator notes"
    }
  ]
}
```

## End-to-end flow

1. **List concepts** to find the internal codes to anchor external IDs:

   ```bash
   sqlite3 path/to/sensiblaw.db \
     "SELECT id, code, label FROM concepts ORDER BY id LIMIT 20;"
   ```

2. **Run `ontology lookup`** by executing a SPARQL search (as above) or another provider-specific query to gather candidate IDs.

3. **Curate JSON** by copying the chosen IDs, labels, and confidence scores into a batch file like `external_refs.json` using the schema above.

4. **Run `ontology external-refs-upsert`** to load the curated batch into SQLite:

   ```bash
   python -m cli ontology external-refs-upsert --db path/to/sensiblaw.db --file external_refs.json
   ```

5. **See results in DB / graph export** by querying the new rows and, if you maintain a graph JSON, re-running your export job before inspecting it with the CLI:

   ```bash
   sqlite3 path/to/sensiblaw.db "SELECT * FROM concept_external_refs LIMIT 5;"
   sqlite3 path/to/sensiblaw.db "SELECT * FROM actor_external_refs LIMIT 5;"

   # After exporting to a graph JSON
   python -m cli graph query --graph path/to/legal_graph.json --type concept --start HOUSING_RENT
   ```

This keeps external knowledge links reviewed, versionable, and deterministic while remaining compatible with the core ontology layers.【F:docs/external_ontologies.md†L24-L118】
