# SensibLaw IR Compression Invariants

These invariants define the non‑negotiable rules for storing and referencing text, tokens, and derived structures. They are the basis for all ingestion, citation following, and graph enrichment work.

## Core invariants

1. **Single lexical authority**  
   Canonical text is stored once per document version. No other table or JSON blob may hold authoritative strings.

2. **Span‑only references**  
   Every higher‑level object (citations, mentions, concepts, rules, graph nodes/edges) references `(doc_id, token_start, token_end)` or an equivalent span; any stored text is debug/cache‑only and discardable.

3. **No duplicate concepts**  
   A normalized concept key maps to exactly one concept row/node. New documents add mentions, not new concept objects for the same key.

4. **Sublinear growth on overlap**  
   Ingesting documents that heavily overlap existing material increases storage primarily via mentions and structure, not by re‑storing text. DB size growth must be materially less than added raw PDF size for overlapping corpora.

5. **Token immutability and idempotence**  
   `(doc_id, token_index)` is unique and stable for a given version. Re‑ingesting the same bytes is idempotent; following citations must not mutate prior token indices.

## Expected data flow

PDF → canonical text → deterministic tokens (whitespace stripped, unicode/ case normalized) → spans → citations / concepts / graph.

Only the token layer owns text; all other layers derive from spans.

## Tests to enforce the invariants

- **Token duplication guard**: ingest the same PDF twice ⇒ token count unchanged for that `doc_id`.  
- **Overlap growth test**: ingest A, then B that quotes A ⇒ token delta for B < 0.7 × tokens(A).  
- **Citation follow stability**: ingest A, record token hash; follow citation to ingest B; token hash of A is unchanged.  
- **Span rehydration**: delete cached snippets; re-render mention/citation text from spans; output matches expectations.  
- **Concept identity**: “abuse of process” / “permanent stay” / “fair trial” occurrences across ingest + text tools resolve to one concept row with multiple mentions.  
- **Research workflow e2e**: upload PDF → unresolved citation badge decrements after follow; DB growth within budget; research-health report metrics reflect changes.
- **Production fixtures**: PDF-backed overlap test (e.g., Mabo) ensures sublinear growth on real sources.
- **Health dashboards**: research-health report publishes `tokens_per_document_mean` to monitor compression drift.
- **Page provenance**: page numbers live in `page_map` metadata (page → token range); they never enter the token stream or affect diffs.

## Operational doctrine

> Text is stored once. Structure is stored many times. Meaning is attached, never duplicated. Growth slows as knowledge accumulates.
