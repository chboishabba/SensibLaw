# Wikidata Queries

*Practical SPARQL patterns for ITIR / SensiBlaw / TiRCorder*

This document collects **small, reusable Wikidata SPARQL patterns** you can call from tooling or copy-paste into the [Wikidata Query Service](https://query.wikidata.org/) when building or debugging external concept mappings.

The focus is on ITIR-relevant tasks:

* finding **people, organisations, agencies**
* classifying **merchants / counterparties**
* finding **legal / housing / medical / social concepts**
* getting **ancestors & categories** for Streamline colouring
* working with **aliases and multilingual labels**

You don’t need all of this in code at once — treat it as a toolbox.

---

## 0. Common Prefixes

Most examples assume these prefixes:

```sparql
PREFIX wd:   <http://www.wikidata.org/entity/>
PREFIX wdt:  <http://www.wikidata.org/prop/direct/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX schema: <http://schema.org/>
```

---

## 1. Searching by Label (basic “I think it’s called X”)

### 1.1 Case-insensitive search in English

```sparql
# Find entities with 'Centrelink' in their label or alias (English)
SELECT ?item ?itemLabel WHERE {
  ?item rdfs:label|skos:altLabel ?label .
  FILTER (LANG(?label) = "en") .
  FILTER (CONTAINS(LCASE(?label), "centrelink")) .
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
LIMIT 20
```

Use this to find the Q-ID you then hard-code into `ConceptExternalRef`.

---

## 2. Constraining by Type (“this must be an org / place / concept”)

Wikidata uses:

* `wdt:P31` = instance of
* `wdt:P279` = subclass of

### 2.1 “Find organisations matching this name”

```sparql
# Likely organisations named something like 'Mercury'
SELECT ?item ?itemLabel WHERE {
  ?item rdfs:label|skos:altLabel ?label .
  FILTER (LANG(?label) = "en") .
  FILTER (CONTAINS(LCASE(?label), "mercury")) .

  # Constrain to organisations (instance-of or subclass-of)
  ?item wdt:P31/wdt:P279* wd:Q43229 .  # Q43229 = organization

  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
LIMIT 50
```

### 2.2 “Find places matching this name”

```sparql
# Places named 'Westmead'
SELECT ?item ?itemLabel ?countryLabel WHERE {
  ?item rdfs:label|skos:altLabel ?label .
  FILTER (LANG(?label) = "en") .
  FILTER (CONTAINS(LCASE(?label), "westmead")) .

  ?item wdt:P31/wdt:P279* wd:Q486972 .     # Q486972 = human settlement
  OPTIONAL { ?item wdt:P17 ?country . }

  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
LIMIT 50
```

---

## 3. Mapping Domain Concepts (housing, domestic violence, welfare, etc.)

These are good seed queries for building concept lists that you then **whitelist** inside ITIR.

### 3.1 Housing & tenancy-related concepts

```sparql
# Core housing / tenancy concepts suitable for a 'housing' tag bucket
SELECT ?item ?itemLabel WHERE {
  VALUES ?root {
    wd:Q167384   # rent
    wd:Q3947     # housing
    wd:Q1195942  # tenancy
  }

  ?item wdt:P279* ?root .   # subclasses of these concepts

  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
LIMIT 200
```

### 3.2 Domestic violence & family violence

```sparql
# Domestic violence and closely related concepts
SELECT ?item ?itemLabel WHERE {
  VALUES ?root {
    wd:Q783794   # domestic violence
    wd:Q56327369 # coercive control
  }

  ?item wdt:P279* ?root .

  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
LIMIT 200
```

### 3.3 Social security / welfare agencies

```sparql
# Agencies similar to Centrelink worldwide
SELECT ?item ?itemLabel ?countryLabel WHERE {
  ?item wdt:P31/wdt:P279* wd:Q327333      . # Q327333 = welfare agency
  OPTIONAL { ?item wdt:P17 ?country . }     # country

  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
LIMIT 200
```

You can cache these results and use them to:

* generate internal concepts,
* drive merchant tagging,
* cluster flows in Streamline.

---

## 4. Getting Ancestors (for Streamline colour/grouping)

Given a concept Q-ID, you often want its **semantic ancestors** for grouping (e.g., “this is housing/health/family/etc.”).

### 4.1 Ancestors via `subclass of` (P279)

```sparql
# All ancestor classes of 'eviction'
# (replace wd:Q41499 with another concept if needed)
SELECT DISTINCT ?ancestor ?ancestorLabel WHERE {
  wd:Q41499 wdt:P279* ?ancestor .
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
LIMIT 200
```

You can use this list to:

* see what *top-level buckets* a concept falls under,
* pick a category like “housing” vs “criminal law” vs “health”.

### 4.2 “Top-ish” ancestor labels

You might want “the highest interesting ancestors” only.

In code, you can:

* fetch all ancestors,
* drop huge generic ones (`entity`, `concept`, `thing`),
* keep a curated set like `HOUSING`, `HEALTH`, `FINANCE`.

---

## 5. Resolving Ambiguity: “Which Mercury?”

### 5.1 Show all “Mercury” entities by type

```sparql
SELECT ?item ?itemLabel ?typeLabel WHERE {
  ?item rdfs:label ?label .
  FILTER (LANG(?label) = "en") .
  FILTER (STR(?label) = "Mercury") .

  OPTIONAL { ?item wdt:P31 ?type . }

  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
LIMIT 50
```

You then filter client-side:

* only accept `type` that is an organisation, bank, etc.,
* fallback to the most frequently used one if multiple.

---

## 6. Working with Aliases & Multilingual Labels

### 6.1 Pull labels & aliases in multiple languages

```sparql
SELECT ?item ?itemLabel ?alias WHERE {
  VALUES ?item { wd:Q783794 }   # domestic violence
  OPTIONAL {
    ?item skos:altLabel ?alias .
    FILTER (LANG(?alias) IN ("en","mi","es"))  # adjust languages
  }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,mi,es". }
}
```

Use this to enrich:

* lexeme lists,
* phrase triggers,
* multilingual recognition.

---

## 7. Linking Counterparties (merchants) to Wikidata

If you have a merchant / agency name from a transaction, you can try to match it.

### 7.1 Fuzzy merchant lookup (label contains “woolworths”)

```sparql
SELECT ?item ?itemLabel ?countryLabel WHERE {
  ?item rdfs:label|skos:altLabel ?label .
  FILTER (LANG(?label) = "en") .
  FILTER (CONTAINS(LCASE(?label), "woolworths")) .

  OPTIONAL { ?item wdt:P17 ?country . }  # country if available

  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
LIMIT 50
```

You can then:

* choose the Q-ID that best matches (e.g., Australian chain),
* store it in `ConceptExternalRef` or `actor_external_refs`,
* tag corresponding transactions.

---

## 8. Legal Topics & Law Areas

Wikidata has law-related entities, but they’re noisy; treat them as hints.

### 8.1 Legal topics / areas of law

```sparql
# Broad "area of law" topics
SELECT ?item ?itemLabel WHERE {
  ?item wdt:P31/wdt:P279* wd:Q1124927 .  # Q1124927 = area of law
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
LIMIT 200
```

You can manually whitelist concepts like:

* family law
* tenancy law
* tort law
* administrative law

and map them to your internal `LegalSystem` / `WrongType` metadata.

---

## 9. Pattern for “search, then bind QID into code”

The expected workflow is:

1. Use a loose query (like those above) in the Wikidata UI to discover **the right Q-ID**.
2. Then hard-code that Q-ID into config / mappings, e.g.:

```jsonc
{
  "concept_code": "HOUSING_RENT",
  "wikidata_qid": "Q167384"
}
```

3. Store as `ConceptExternalRef` records in your DB.

This avoids hitting SPARQL live for every request, and keeps critical mappings **deterministic and reviewable**.

---

## 10. Implementation Tips

* **Cache responses** for any SPARQL use in production (daily/weekly refresh is fine).
* Use **offline dumps** (Wikidata JSON) for high-security deployments instead of live HTTP.
* Treat results as **candidates**, not ground truth — always pass through a small curation layer when creating or updating `ConceptExternalRef`.
* Maintain a tiny local file `wikidata_seeds.json` that lists:

  * known Q-IDs,
  * their internal concept codes,
  * and any manual notes.

Example:

```jsonc
[
  {
    "concept_code": "DOMESTIC_VIOLENCE",
    "provider": "wikidata",
    "external_id": "Q783794",
    "notes": "Use for concept grouping and Streamline colouring; not for legal classification."
  }
]
```

---

If you’d like, I can also draft:

* a **`wikidata_integration_pipeline.md`** (how to go from text → candidates → curated mappings), or
* a small **Python helper module** (`external_ontologies/wikidata_client.py`) with ready-made functions corresponding to these query patterns.
