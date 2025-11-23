# External Source Ingestion & Table Population

This note explains how external providers populate SensibLaw tables and seed files. It focuses on two supported paths today:

- **Wikidata / Wikibase-style sources ("wikidb")** that enrich ontology rows via `concept_external_refs` and `actor_external_refs`.
- **Pol.is** conversations that are converted into concept seeds for later loading or proof-pack generation.

## Target storage

- The ontology tables `concept_external_refs` and `actor_external_refs` capture links to outside identifiers (e.g., Wikidata Q-IDs) with uniqueness enforced on `(concept_id, provider, external_id)` and `(actor_id, provider, external_id)` respectively.【F:database/migrations/002_concept_substrate.sql†L40-L65】
- Pol.is statements are written as JSON seed files under `data/concepts/` in the same `{"concepts": [...], "relations": []}` envelope used elsewhere in the project.【F:src/ingest/polis.py†L1-L205】

## Wikidata / Wikibase ingestion ("wikidb")

1. **Find candidates.** Choose a SPARQL snippet from `docs/wikidata_queries.md` (for fuzzy name or category lookups) and run it against the public endpoint to gather candidate IDs and labels.【F:docs/ONTOLOGY_EXTERNAL_REFS.md†L13-L34】
2. **Curate a batch.** Assemble chosen IDs into a JSON file following the `concept_external_refs` / `actor_external_refs` payload structure that records the internal concept code or actor ID, provider (`wikidata`/`dbpedia`/`yago`/`wordnet`), external ID, label, and optional confidence score.【F:docs/ONTOLOGY_EXTERNAL_REFS.md†L36-L73】
3. **Upsert into SQLite.** Run the documented Python snippet to translate `concept_code` to `concept_id` and insert or refresh rows in both tables using `ON CONFLICT` to keep deduplicated links.【F:docs/ONTOLOGY_EXTERNAL_REFS.md†L75-L108】
4. **Verify and export.** Query the tables to confirm the ingest, then re-run any graph export jobs (with `--include-external-refs` where relevant) so downstream tools see the new `owl:sameAs` / `skos:exactMatch` triples.【F:docs/ONTOLOGY_EXTERNAL_REFS.md†L110-L119】

## Pol.is conversation ingestion

1. **Pull statements.** Use the CLI to fetch a conversation and rank statements with retry/backoff support:
   ```bash
   python -m cli polis import --conversation <CONVO_ID> --out ./packs/polis --limit 50
   ```
   The handler calls `fetch_conversation`, applies optional `--limit`, and writes the ranked seed payload while building proof packs under the requested output directory.【F:cli/__main__.py†L387-L404】【F:cli/__main__.py†L1129-L1138】
2. **Seed structure.** Each Pol.is statement becomes a seed entry with an ID, label, and optional cluster label, and the module persists the `{"concepts": [...], "relations": []}` JSON to `data/concepts/polis_<CONVO_ID>.json` for later loading into the knowledge base or manual review.【F:src/ingest/polis.py†L124-L205】
3. **Cache and throttling.** The importer caches responses per conversation/limit pair and retries HTTP 429/5xx responses using configurable `--max-retries` and `--sleep-between-retries` flags (falling back to `SENSIBLAW_MAX_RETRIES` / `SENSIBLAW_SLEEP_BETWEEN_RETRIES`). This keeps ingestion resilient against API rate limits while ensuring deterministic output files.【F:src/ingest/polis.py†L39-L170】

## Adding new external sources

Follow the same patterns: resolve source identifiers to internal concept or actor keys, curate a JSON batch matching the external ref schema, then upsert via SQLite so exports can emit explicit cross-ontology links. For content-centric feeds (e.g., civic debate platforms), normalize results into the seed envelope used by Pol.is so they can flow through the same concept-loading and proof-pack tooling.【F:docs/ONTOLOGY_EXTERNAL_REFS.md†L36-L108】【F:src/ingest/polis.py†L124-L205】
