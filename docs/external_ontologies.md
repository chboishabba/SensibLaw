# External Ontologies & World Knowledge Integration

*How ITIR leverages Wikidata, DBpedia, YAGO, WordNet & related knowledge systems*

---

## 1. Purpose

ITIR is built on a **structured, evidence-centred ontology** (events, actors, legal duties, harm types, protected interests, financial flows, utterances, and provenance).
However, the real world contains **far more background knowledge** than we should maintain manually.

External ontologies — especially **Wikidata, DBpedia, YAGO, WordNet, Umbel, and other Wikitology-style sources** — give us:

* Broad, multilingual general-knowledge graphs
* Stable IDs for people, places, organisations, and generic concepts
* Hierarchical “is-A” taxonomies
* Common-sense relationships
* Cross-lingual synonyms & alternative labels
* Pretrained graph embeddings for semantic search

The goal is to **use these as enrichment**, not as normative legal reasoning sources.

This document describes **how external ontologies attach to ITIR’s internal structures** without contaminating the legal layers.

---

## 2. Integration Principles

### 2.1 External Ontologies Are *Advisory*, Never Normative

Your internal ontology layers (L1–L6):

* Events
* Claims & Cases
* Norm Sources & Provisions
* Wrong Types & Duties
* Protected Interests & Harms
* Value Frames & Remedies

remain **authoritative**.

External entities **cannot**:

* create new WrongTypes or Duties,
* infer legal liability,
* add normative claims,
* override jurisdiction-specific logic.

They only enrich interpretation, search, and clustering.

---

## 3. Where External Ontologies Plug Into the Architecture

External ontologies connect into:

### ✔️ Layer 0 (Text & Concept Substrate)

**Lexeme → Concept → ExternalReference**

```
Lexeme ----> Concept ----> ConceptExternalRef
                     (provider='wikidata', id='Q12345')
```

This is the safest and most powerful integration point.

**Benefits:**

* disambiguation (“Mercury” = credit union, not planet)
* better concept grouping (housing, family, medical, legal-process, etc.)
* world-knowledge embeddings improve matching & snippet ranking
* cross-lingual robustness
* richer phrase detection (“best interests of the child” connects to Q43014)

### ✔️ Layer 1 (Events & Actors)

Actors, places, organisations can be linked to Wikidata/DBpedia entities.

Example:

```
Actor(id=12, label="Westmead Hospital")
  ↳ external_ref: wikidata Q1035965
```

This improves:

* NER accuracy
* concept grounding
* narrative summarisation
* Streamline’s event labelling

### ✔️ Finance Layer

Transactions often describe:

* merchants
* organisations
* locations
* government agencies

External ontologies can classify the **counterparty**:

* Q968159 → “Woolworths”
* Q5065980 → “Centrelink”
* Q783794 → “Domestic violence services” (if NGO)

This strengthens:

* branch labelling in Streamline
* spending category inference
* fraud / cycle detection (better community detection)

### ✔️ Streamline Visualisation

Streamline can auto-colour or group items by external ontology categories.

Example:

* Housing cluster (rent, bond, arrears, electricity bill)
* Transport cluster (fuel, repairs, insurance)
* Health cluster (GP visits, prescriptions)

Colouring & grouping become **data-driven**, not hand-written.

---

## 4. Schema Additions

Add a single, clean join table:

```sql
CREATE TABLE concept_external_refs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    concept_id    INTEGER NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
    provider      TEXT NOT NULL,            -- 'wikidata','dbpedia','yago','wordnet'
    external_id   TEXT NOT NULL,            -- Q-ID, full URI, synset ID
    external_url  TEXT,                     -- optional: canonical URL (often same as external_id for URI providers)
    notes         TEXT,                     -- optional curator notes / type hints
    UNIQUE (concept_id, provider, external_id)
);
```

Optionally, a similar structure for Actors:

```sql
CREATE TABLE actor_external_refs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id      INTEGER NOT NULL REFERENCES actors(id) ON DELETE CASCADE,
    provider      TEXT NOT NULL,
    external_id   TEXT NOT NULL,
    external_url  TEXT,
    notes         TEXT,
    UNIQUE (actor_id, provider, external_id)
);
```

---

## 5. Knowledge Sources Supported

### ✔️ Wikidata (Primary)

* Multilingual
* Dense graph structure
* Good for actors, organisations, places, abstract concepts
* Rich type system (Q5 = human, Q43229 = organisation)

### ✔️ DBpedia

* RDF-oriented
* Good for definitions, synonyms, infobox fields

### ✔️ YAGO

* More strongly typed
* Good for higher-level taxonomy inference

### ✔️ WordNet

* Synsets & lexical categories
* Good for fallback matching and phrase normalisation
* Excellent for sentiment or psychological-category enrichment

### ✔️ Umbel / Schema.org

* Broad conceptual categories
* Useful for organising Streamline visual groupings

---

## 6. Workflow: Phrase → Candidate Entity → Curated Concept

A safe integration pipeline:

### Step 1: Detection

Lexeme or Phrase triggers hit local rules (Aho-Corasick, regex).

### Step 2: Candidates from Wikidata / DBpedia

Simple SPARQL queries:

* search by label
* search by alias
* search by category

### Step 3: Filter

Discard:

* irrelevant domains
* metaphoric uses
* generic abstract entities (“concept”, “idea”)

### Step 4: Curate

Human or rule-based mapping to **internal Concept**.

### Step 5: Store external references

For each approved mapping:

```
ConceptExternalRef:
  concept = ITIR:HOUSING_RENT
  provider = 'wikidata'
  external_id = 'Q167384'
```

### Final Output

Lexemes map to Concepts; Concepts map to world knowledge.

---

## 7. How External Ontologies Help Each Layer of ITIR

### Layer 0 — Text

Better disambiguation, lexeme clustering, phrase detection.

### Layer 1 — Events

Places, organisations, life domains get structured identifiers.

### Layer 2 — Claims & Cases

World concepts can suggest relevant legal categories.

### Layer 3 — Provisions

Better cross-jurisdictional search (“eviction law” = subset of housing law).

### Layer 4 — Wrong Types & Duties

Helps distinguish similar-sounding harms.

### Layer 5 — Protected Interests

External ontologies supply thematic clusters (safety, bodily integrity, shelter, family stability).

### Layer 6 — Value Frames

Can reference cultural, community, or health domains recognised in Wikidata/YAGO.

### Finance Layer

Semantic classification of counterparties and merchants.

### Streamline

Automatically groups & colours:

* spending domains
* predicted harm categories
* life themes
* narrative arcs

---

## 8. Why This Approach Is Safe

Because:

* External ontologies only **decorate** Concepts; they never *create* WrongTypes.
* Normative edges stay internal.
* No external entity can dictate harm classification or responsibility.
* Provenance always ties back to **sentences**, never external facts.

This ensures the system remains:

* jurisdiction-aware
* culturally respectful
* audit-friendly
* explainable

while still benefitting from world-scale semantic context.

---

## 9. Future Extensions

* Caching labels & summaries from Wikidata
* Optional offline Wikidata dump for secure deployments
* Graph embeddings for:

  * concept similarity
  * cluster prediction
  * story theme extraction
* Community-level concepts (tikanga, indigenous law frameworks) with external alignment
* Multi-ontology alignment layer (Wikidata ↔ WordNet ↔ Schema.org)

---

## 10. Summary

External ontologies enable ITIR to:

* understand the world without bloating its own ontology
* disambiguate language and events
* semantically enrich financial and narrative flows
* improve visualisation & clustering in Streamline
* strengthen cross-lingual and multicultural robustness

…while keeping **legal reasoning**, **harm classification**, and **provenance** strictly internal, grounded in evidence and jurisdiction.
