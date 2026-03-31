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

### 2.2 Two Distinct Wikidata Uses

Wikidata work in SL/ITIR currently has two separate surfaces:

1. **External reference curation**
   - reviewed QID attachment to `concept_external_refs` and
     `actor_external_refs`
   - identity linking only
2. **Diagnostic control-plane**
   - read-only projection and structural review over Wikidata statement bundles
   - stability/volatility reporting (`EII`, SCCs, mixed-order diagnostics)

These surfaces must not be conflated. External-ref curation is not a reasoner,
and diagnostic findings do not redefine internal ontology rows.

### 2.3 Provider-Backed Enrichment Helpers

In addition to read-only lookup and curated external-ref import, the current
ontology surface may include bounded helper commands that:

* query provider APIs such as Wikidata and DBpedia
* rank or filter candidate matches with deterministic heuristics
* emit a reviewable candidate payload for batch curation
* optionally upsert selected candidates into `concept_external_refs` and
  `actor_external_refs`

These helpers are still enrichment-only. They must not:

* replace the internal ontology
* infer legal truth
* mutate tables outside the curated external-ref path
* bypass reviewed IDs by auto-promoting provider candidates without operator
  review

### 2.4 No Metaclass Escalation During Mapping

When curating external IDs, do not import Wikidata metaclass structure into the
internal ontology as if it were canonical truth.

Rules:
- a QID link is an identity anchor, not an ontology transplant
- external class structure may be stored as notes or review context, not as
  authoritative legal ontology
- `P31` / `P279` complexity in Wikidata must remain outside canonical
  `WrongType`, `ProtectedInterestType`, `ValueFrame`, and related authority
  layers unless separately modeled internally

### 2.4 Tokenizer / Lexeme Boundary

Canonical text, token, and lexeme layers remain pre-semantic and authoritative
for provenance.

This means:
- lexemes must not carry Wikidata identity
- tokenizer identity is not ontology identity
- external ontology linking and diagnostics operate over curated IDs, actors,
  concepts, and Wikidata statement bundles, not over canonical token identity

See:
- `docs/tokenizer_contract.md`
- `docs/lexeme_layer.md`
- `docs/extractor_ontology_mapping_contract_20260213.md`
- `docs/planning/extraction_enrichment_boundary_20260307.md`

### 2.5 spaCy / Parser Boundary For Relation Inference

`spaCy` and related local parser/dependency tooling may be used as a
deterministic structural backup for relation and role harvesting, but not as a
source of canonical ontology truth.

In practice:
- the parser layer may supply local syntax signals such as subject/object arcs,
  clause boundaries, local attachment structure, and argument candidates
- those signals may support downstream extraction of actors, predicates,
  modality, and candidate relations
- parser output must remain version-pinned and reproducible for the same local
  model/resources
- parser output must not redefine canonical token identity or ontology rows by
  itself

This creates a strict split:
- `tokenizer / lexeme layer` = canonical, deterministic, provenance-bearing
- `spaCy / parser layer` = deterministic structural evidence for extraction
- `Wikidata / external ontology layer` = downstream identity enrichment,
  candidate checking, and diagnostics

External ontologies may help *flesh out* or *check* candidate relations and
entity links, but they do so only after local deterministic extraction has
produced the candidate structure.

For corpus reporting, this means a valid deterministic workflow is:
- local parser (`spaCy`) derives top recurring actors/topics plus dependency or
  sentence-neighborhood evidence for them
- the reviewed bridge/Wikidata slice checks whether any of those recurring
  terms already map to pinned external identities
- the report surfaces both layers side by side instead of collapsing them into
  one "truth" output

---

## 3. Where External Ontologies Plug Into the Architecture

External ontologies connect into:

### ✔️ Layer 0 (Text & Concept Substrate)

**Lexeme → Concept → ExternalReference**

```
Lexeme ----> Concept ----> ConceptExternalRef
                     (provider='wikidata', id='Q12345')
```

This is the safest integration point for curated identity links, provided the
boundary is respected: lexemes remain pre-semantic, and the external reference
attaches to the curated internal concept rather than mutating the lexeme layer.

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

#### Deterministic Mapping Policy (SL/ITIR)
- WordNet may be used as a deterministic semantic backbone for normalization only.
- Any authoritative mapping that uses WordNet synsets must be:
  - version-pinned (validated at runtime),
  - deterministic (rule-first; no generative WSD),
  - and driven by explicit curated mappings (synset -> canonical label).

### ✔️ Umbel / Schema.org

* Broad conceptual categories
* Useful for organising Streamline visual groupings

---

## 6. Workflow: Phrase → Candidate Entity → Curated Concept

A safe integration pipeline:

### Step 1: Detection

Lexeme or Phrase triggers hit local rules.

In authoritative paths, tokenizer/lexeme handling remains deterministic and
pre-semantic; regex or heuristic triggers are discovery aids, not ontology
identity.

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

The reverse is not allowed: external ontologies must not redefine lexeme
identity, canonical spans, or internal legal ontology authority boundaries.

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
