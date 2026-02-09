# DBpedia SPARQL Query Patterns (Curation-Time)

This document is the DBpedia analogue of `docs/wikidata_queries.md`:

- query DBpedia only for **advisory enrichment** (actors + general concepts)
- curate results into `concept_external_refs` / `actor_external_refs`
- do not treat DBpedia output as normative truth

Endpoint:

- `http://dbpedia.org/sparql`
- (alt) `http://live.dbpedia.org/sparql`

Lookup service (often more reliable than SPARQL for simple name -> URI resolution):

- `http://lookup.dbpedia.org/api/search?format=JSON&query=...`

## 1) Label lookup (substring; English)

```sparql
PREFIX dbo: <http://dbpedia.org/ontology/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT ?item ?label ?abstract ?type WHERE {
  ?item rdfs:label ?label .
  FILTER (lang(?label) = "en") .
  FILTER (CONTAINS(LCASE(STR(?label)), "westmead hospital")) .

  OPTIONAL {
    ?item dbo:abstract ?abstract .
    FILTER (lang(?abstract) = "en") .
  }
  OPTIONAL {
    ?item rdf:type ?type .
    FILTER (STRSTARTS(STR(?type), "http://dbpedia.org/ontology/")) .
  }
}
LIMIT 25
```

## 2) Label lookup with type filter (dbo:Hospital)

```sparql
PREFIX dbo: <http://dbpedia.org/ontology/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?item ?label ?abstract WHERE {
  ?item a dbo:Hospital .
  ?item rdfs:label ?label .
  FILTER (lang(?label) = "en") .
  FILTER (CONTAINS(LCASE(STR(?label)), "westmead")) .
  OPTIONAL {
    ?item dbo:abstract ?abstract .
    FILTER (lang(?abstract) = "en") .
  }
}
LIMIT 25
```

## 3) Resolve redirects (when you already have a URI)

DBpedia often represents redirects via `dbo:wikiPageRedirects`.

```sparql
PREFIX dbo: <http://dbpedia.org/ontology/>

SELECT ?target WHERE {
  <http://dbpedia.org/resource/Westmead_Hospital> dbo:wikiPageRedirects ?target .
}
LIMIT 10
```

## 4) Minimal “entity profile” (types + categories)

```sparql
PREFIX dct: <http://purl.org/dc/terms/>
PREFIX dbo: <http://dbpedia.org/ontology/>

SELECT ?type ?cat WHERE {
  OPTIONAL { <http://dbpedia.org/resource/Westmead_Hospital> a ?type . }
  OPTIONAL { <http://dbpedia.org/resource/Westmead_Hospital> dct:subject ?cat . }
}
LIMIT 200
```

## 5) How we use results in ITIR/SL

- **Primary use**: attach reviewed external IDs to internal nodes:
  - `actor_external_refs(provider="dbpedia", external_id="<full DBpedia URI>")`
  - `concept_external_refs(provider="dbpedia", external_id="<full DBpedia URI>")`
- **Not allowed**: importing DBpedia classes as authoritative WrongTypes/Duties/etc.
- **Recommended storage**: store DBpedia IDs as full URIs (not `dbpedia:...`).

See also:
- `docs/ONTOLOGY_EXTERNAL_REFS.md`
- `docs/external_ingestion.md`
