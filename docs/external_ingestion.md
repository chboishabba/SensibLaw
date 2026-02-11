# External Source Ingestion & Table Population

This note explains how external providers populate SensibLaw tables and seed files. It focuses on two supported paths today:

- **Wikidata / Wikibase-style sources ("wikidb")** that enrich ontology rows via `concept_external_refs` and `actor_external_refs`.
- **Pol.is** conversations that are converted into concept seeds for later loading or proof-pack generation.

## Target storage

- The ontology tables `concept_external_refs` and `actor_external_refs` capture links to outside identifiers (e.g., Wikidata Q-IDs) with uniqueness enforced on `(concept_id, provider, external_id)` and `(actor_id, provider, external_id)` respectively.【F:database/migrations/002_concept_substrate.sql†L40-L65】
- Pol.is statements are written as JSON seed files under `data/concepts/` in the same `{"concepts": [...], "relations": []}` envelope used elsewhere in the project.【F:src/ingest/polis.py†L1-L205】

## Wikidata / Wikibase ingestion ("wikidb")

1. **Find candidates.** Choose a SPARQL snippet from `docs/wikidata_queries.md` (for fuzzy name or category lookups) and run it against the public endpoint to gather candidate IDs and labels.【F:docs/ONTOLOGY_EXTERNAL_REFS.md†L13-L34】
2. **Curate a batch.** Assemble chosen IDs into a JSON file following the `concept_external_refs` / `actor_external_refs` payload structure that records the internal concept code or actor ID, provider (`wikidata`/`dbpedia`/`yago`/`wordnet`), external ID, and optional `external_url`/`notes`.【F:docs/ONTOLOGY_EXTERNAL_REFS.md†L36-L73】
3. **Upsert into SQLite.** Run the CLI helper to translate `concept_code` to `concept_id` and insert or refresh rows in both tables using `ON CONFLICT` to keep deduplicated links.【F:docs/ONTOLOGY_EXTERNAL_REFS.md†L75-L108】
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

## AU legal-principles bootstrap source pack

For AU doctrinal-principle intake (benchbooks + primary authority discovery),
start from:

- `SensibLaw/data/source_packs/legal_principles_au_v1.json`

This pack is intentionally tiered:

- Primary authority discovery (`AustLII`, official court/statute paths)
- Structured doctrine guidance (Judicial College / AIJA / FWC benchbooks)
- Identity/disambiguation support (wiki connector seeds only)

Rules for this pack:

- Benchbooks are support lanes, not authority truth.
- Citation following remains bounded and citation-driven.
- Wiki connector is identity glue only; never doctrinal authority.
- Output lanes stay split (`citations[]` hints vs `sl_references[]` parser-native refs).

Run the bounded puller:

```bash
.venv/bin/python SensibLaw/scripts/source_pack_manifest_pull.py \
  --pack SensibLaw/data/source_packs/legal_principles_au_v1.json \
  --timeout 20
```

Default outputs (gitignored) under:

- `SensibLaw/demo/ingest/legal_principles_au_v1/manifest.json`
- `SensibLaw/demo/ingest/legal_principles_au_v1/timeline.json`
- `SensibLaw/demo/ingest/legal_principles_au_v1/timeline_graph.json`
- `SensibLaw/demo/ingest/legal_principles_au_v1/wiki_timeline_legal_principles_au_v1.json`

Bounded authority follow pass from the first manifest:

```bash
.venv/bin/python SensibLaw/scripts/source_pack_authority_follow.py \
  --manifest SensibLaw/demo/ingest/legal_principles_au_v1/manifest.json \
  --max-depth 2 \
  --max-new-docs 40 \
  --timeout 20
```

Follow outputs (gitignored) under:

- `SensibLaw/demo/ingest/legal_principles_au_v1/follow/follow_manifest.json`
- `SensibLaw/demo/ingest/legal_principles_au_v1/follow/follow_timeline.json`
- `SensibLaw/demo/ingest/legal_principles_au_v1/follow/follow_timeline_graph.json`
- `SensibLaw/demo/ingest/legal_principles_au_v1/follow/wiki_timeline_legal_principles_au_v1_follow.json`

## High Court case demo bundle (`case-s942025`)

Use `SensibLaw/scripts/hca_case_demo_ingest.py` to pull a single High Court case page, download linked artifacts, ingest PDFs, and emit graph + media sidecars into a gitignored demo folder:

```bash
.venv/bin/python SensibLaw/scripts/hca_case_demo_ingest.py --timeout 60 --no-video-download
```

If `dot` is not on PATH in your current shell, pass it explicitly:

```bash
.venv/bin/python SensibLaw/scripts/hca_case_demo_ingest.py --timeout 60 --dot-bin /path/to/dot
```

Output root:

- `SensibLaw/demo/ingest/hca_case_s942025/manifest.json` (download manifest + unresolved rows)
- `SensibLaw/demo/ingest/hca_case_s942025/ingest/ingest_report.json` (PDF ingest results)
- `SensibLaw/demo/ingest/hca_case_s942025/graph/case_bundle.graph.json` (graph payload)
- `SensibLaw/demo/ingest/hca_case_s942025/media/media_report.json` (recording/captions/transcript metadata)
- `SensibLaw/.cache_local/wiki_timeline_hca_s942025_aoo.json` (Svelte AAO payload with tagged signal lanes)
- `SensibLaw/demo/ingest/hca_case_s942025/sb_signals.json` (observer-signal export for SB ingestion)

Important details:

- Document-table link selection is scored per label so `Judgment (Judgment Summary)` resolves to the summary PDF (not the judgment HTML page).
- Recording ingestion uses a two-path strategy:
  - Preferred: Vimeo caption tracks (`.vtt` + timestamped transcript markdown/json).
  - Fallback: transcript links on the AV recording page (e.g., AustLII hearing transcript HTML/text).
- Some recordings expose only HLS/DASH manifests (no progressive MP4 URL). The ingest writes manifest files under `media/video/` so playback/downloader tooling can consume them later.
- `Notice of appeal` may remain `missing_url` when the case documents table does not provide a public hyperlink.

### Parsing contract for HCA AAO payloads (current interim path)

`hca_case_demo_ingest.py` currently emits two distinct event lanes into
`SensibLaw/.cache_local/wiki_timeline_hca_s942025_aoo.json`:

- `artifact_status` lane:
  - derived from the case-page documents table and media extraction status
    (`downloaded`, `missing_url`, `error`).
  - examples: hearing rows, filing rows, caption/manifest extraction rows.
- `narrative_sentence` lane:
  - derived from sentence text extracted from ingested case artifacts
    (`*.document.json` bodies/sentences).
  - expanded through the same sentence-local AAO parser used for wiki timeline
    views (`wiki_timeline_aoo_extract.py`), then merged back into the HCA AAO
    payload.
- includes deterministic citation extraction (`SC[210]`, `AS[27]-[29]`,
    `CAB 55`, footnote markers) as structured `citations[]` on each event.
  - includes SL parser-native reference joins as `sl_references[]`, sourced
    from provision/rule-atom reference lanes in each source `document_json`
    artifact with provenance (`source_document_json`, `provision_stable_id`,
    `rule_atom_stable_id`).
  - includes parser-native context lanes for narrative events:
    - `party` (derived parser-first from document structure: TOC, metadata, sentence lane cues;
      falls back to source-label mapping only when structure is unresolved)
    - `party_source` / `party_evidence` / `party_scores` for auditability of role attribution
    - `toc_context[]` (sentence->TOC overlap against `document_json.toc_entries`)
    - `legal_section_markers` (`citation_prefixes`, `sl_reference_lanes`,
      `provision_stable_ids`, `rule_atom_stable_ids`)
    - `timeline_facts[]` (step-local fact rows with date anchors extracted from
      sentence DATE entities; fallback to event anchor when no DATE mention)

`wiki_timeline_hca_s942025_aoo.json` also emits `fact_timeline[]` at top level:

- flattened union of narrative `timeline_facts[]`
- sorted by parsed fact anchor (`year, month, day`)
- intended for linear-time display when source prose is argumentative/out-of-order

This is intentionally an **adapter**, not a canonical legal interpretation pass:

- sentence-local only
- non-causal
- non-authoritative
- provenance-preserving (each narrative event points back to source artifact)
- deterministic parser-first filtering (token/POS/dependency features) with regex reserved for fallback hygiene only.

### SB signal handoff expectation

Even when this path is not the final intended legal pipeline, these records are
still valid observer signals for StatiBaker:

- `artifact_status` events -> operational ingest progress and evidence presence.
- `narrative_sentence` AAO events -> provisional timeline/actor/action/object
  signals for review surfaces.
- `citations[]` -> review-time follower hints with ordered providers
  (`wikipedia` first, then `wiki_connector`, then source document/pdf).
- `sl_references[]` -> parser-native reference lane for structured joins into
  SL artifacts while remaining observer-only at this stage.

These lanes must remain explicitly tagged and reversible so SB consumes them as
observer inputs, never as normative truth.

### Hardcoded vs algorithmic (HCA adapter)

- Hardcoded:
  - case seed plan rows (`_build_doc_plan`) for the specific HCA demo bundle
  - bounded source-label fallback for party when structure parsing remains unresolved
- Algorithmic/deterministic:
  - sentence gating + AAO extraction (spaCy parser-first, wiki AAO adapter)
  - citation extraction lane (`citations[]`) and parser-native reference joins (`sl_references[]`)
  - party inference from document structure (`toc_entries`, metadata, sentence token cues)
  - TOC matching (`toc_context[]`) via token-overlap scoring against extracted `toc_entries`
  - legal markers (`legal_section_markers`) composed from citation prefixes and SL reference provenance
  - fact chronology lane (`timeline_facts[]`/`fact_timeline[]`) from DATE entity anchors + extracted AAO steps

### SL parser reuse status

- Reused now:
  - PDF ingest outputs: `provisions`, `rule_tokens.references`, `rule_atoms.references`,
    `toc_entries`, sentence segmentation artifacts
  - Narrative reference join lane: sentence -> SL references with provenance
- Not yet wired in this adapter:
  - full rule-level legal proposition parsing as primary AAO source
  - court-argument role ontology (beyond coarse `party`) and adjudicative stance classification
