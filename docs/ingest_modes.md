# Ingest modes and large-document handling

## Modes

- **legal** (default): applies citation detection/resolution, provenance logging, and refuses to treat a document as an authority unless basic legal signals are present (citations, section markers, court/jurisdiction hints). Follows all IR invariants.
- **general**: accepts arbitrary evidence/content; skips legal enrichers; still tokenises canonically and records spans. Intended for uploads such as briefs, emails, chat logs, or technical appendices.

Both modes share the same parser and token/spans; only enrichers and gating differ.

## Page numbers

- Page numbers are provenance, not meaning.
- Do **not** enter the canonical token stream.
- Store once per revision as a `page_map`:
  - `page_number -> (token_start, token_end)`
  - referenced by spans when rendering or exporting “p. N” citations.
- Never diff on page boundaries; spans remain the stable locator.

## Large-document path (applies to both modes)

Triggered when any of:
- tokens > 25k
- chars > 200k
- pages > 40

Behaviour:
- **Pre-strip deterministic boilerplate**: drop lines that repeat on most pages (headers/URLs) and record them in metadata (`prestrip: [...]`).
- **Chunking**: 4k-token segments with 20% overlap; segments belong to the same document ID; spans carry chunk offsets.
- **Repetition metrics** (metadata only, no dedupe):
  - `repeat_ratio` (share of repeated 5-grams)
  - `max_chunk_jaccard`
  - `chunk_count`
- **Enricher gating**:
  - Tokens/spans always stored.
  - Legal enrichers (citations/structure/concepts) run only if legal signals are present or `--force-legal` is set.

## Planned tests

- Page-map stability: two paginated PDFs of the same judgment yield identical tokens, differing page_map; spans remain valid.
- Large-doc bounded ingest: very large non-legal PDF ingests successfully, is chunked, records repetition metadata, and leaves prior doc token hashes unchanged.
- Mode separation: same file ingested as `general` vs `legal`; tokens identical, legal enrichers gated unless forced.
- Generic corpus stats: `scripts/corpus_stats.py` provides worker-parallel PDF token/overlap metrics with the shared tokenizer for growth audits on arbitrary corpora.
