# External Ontology References

This guide explains how to attach SensibLaw concepts and actors to external ontology identifiers (e.g., Wikidata, DBpedia, YAGO, WordNet) using the `concept_external_refs` and `actor_external_refs` tables. It also shows how to look up candidates, curate a JSON batch, and upsert the links so they appear in the database and downstream graph exports.

## Table overview

- **`concept_external_refs`** stores external IDs against canonical concepts. Each row records the `concept_id`, `provider` (e.g., `wikidata`), `external_id` (such as a Q-ID), optional `label`, and a `confidence` score. A `(concept_id, provider, external_id)` tuple is unique to avoid duplicates.【F:docs/external_ontologies.md†L128-L160】
- **`actor_external_refs`** mirrors the pattern for people, organisations, and places with `actor_id`, `provider`, `external_id`, and `confidence` fields.【F:docs/external_ontologies.md†L162-L181】

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

## JSON batch format

Curate lookups into a single JSON payload that separates concept and actor inserts. The `concept_code` is resolved to `concept_id` during upsert, while actor rows use the primary key you already have in your database.

```json
{
  "concept_external_refs": [
    {
      "concept_code": "HOUSING_RENT",
      "provider": "wikidata",
      "external_id": "Q167384",
      "label": "renting",
      "confidence": 0.86
    }
  ],
  "actor_external_refs": [
    {
      "actor_id": 42,
      "provider": "wikidata",
      "external_id": "Q1035965",
      "label": "Westmead Hospital",
      "confidence": 0.91
    }
  ]
}
```

## End-to-end flow

1. **List concepts** to find the internal codes to anchor external IDs:

   ```bash
   sqlite3 path/to/sensiblaw.db \
     "SELECT id, code, label FROM concept ORDER BY id LIMIT 20;"
   ```

2. **Run `ontology lookup`** by executing a SPARQL search (as above) or another provider-specific query to gather candidate IDs.

3. **Curate JSON** by copying the chosen IDs, labels, and confidence scores into a batch file like `external_refs.json` using the schema above.

4. **Run `ontology upsert`** to load the curated batch into SQLite. This helper keeps existing rows and refreshes labels/confidence on conflicts:

   ```bash
   python - <<'PY'
   import json, sqlite3

   payload = json.load(open("external_refs.json"))
   conn = sqlite3.connect("path/to/sensiblaw.db")
   cur = conn.cursor()

   for row in payload.get("concept_external_refs", []):
     cur.execute(
       """
       INSERT INTO concept_external_refs (concept_id, provider, external_id, label, confidence)
       VALUES ((SELECT id FROM concept WHERE code = ?), ?, ?, ?, ?)
       ON CONFLICT(concept_id, provider, external_id)
       DO UPDATE SET label = excluded.label, confidence = excluded.confidence;
       """,
       (row["concept_code"], row["provider"], row["external_id"], row.get("label"), row.get("confidence", 1.0)),
     )

   for row in payload.get("actor_external_refs", []):
     cur.execute(
       """
       INSERT INTO actor_external_refs (actor_id, provider, external_id, label, confidence)
       VALUES (?, ?, ?, ?, ?)
       ON CONFLICT(actor_id, provider, external_id)
       DO UPDATE SET label = excluded.label, confidence = excluded.confidence;
       """,
       (row["actor_id"], row["provider"], row["external_id"], row.get("label"), row.get("confidence", 1.0)),
     )

   conn.commit()
   conn.close()
   PY
   ```

5. **See results in DB / graph export** by querying the new rows and, if you maintain a graph JSON, re-running your export job before inspecting it with the CLI:

   ```bash
   sqlite3 path/to/sensiblaw.db "SELECT * FROM concept_external_refs LIMIT 5;"
   sqlite3 path/to/sensiblaw.db "SELECT * FROM actor_external_refs LIMIT 5;"

   # After exporting to a graph JSON
   python -m cli graph query --graph path/to/legal_graph.json --type concept --start HOUSING_RENT
   ```

This keeps external knowledge links reviewed, versionable, and deterministic while remaining compatible with the core ontology layers.【F:docs/external_ontologies.md†L24-L118】
