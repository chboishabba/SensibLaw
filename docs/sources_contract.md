# Sources Contract (Search vs Fetch)

## Core rule
**Search adapters return references; fetch adapters return bytes.**  
No adapter tokenises, parses, deduplicates, or infers. Semantics begin only after ingestion.

## Adapters

- **AustLII SINO (search)**  
  - API: `search(query, meta/vc, method, results, offset, mask_path|mask_phc)`  
  - Returns: list of `{title, url, citation?, database_heading?}`  
  - Deterministic URL builder, polite rate limit (default 0.5 rps, burst 1).
  - No crawling or pagination beyond explicit `offset + results`.

- **AustLII fetch (document)**  
  - Input: explicit AustLII URL (HTML/PDF).  
  - Returns: raw bytes + provenance (url, path, content_type, status_code).  
  - Rejects non-AustLII URLs. Default 1 rps.

- **JADE fetch (document)**  
  - Input: citation or constructed URL.  
  - Returns: raw bytes + provenance.  
  - No API key assumed; semantic-free.

## Citation-following (bounded)
- Expansion is **citation-driven**, not crawling.
- Bounds required: `max_depth` and `max_new_docs` (both must be set).
- Resolution order: already-ingested → local PDF → JADE (exact MNC) → AustLII (explicit URL or search) → unresolved.
- Provenance recorded (source, citation, citing_doc) but kept out of identity hashes.

## Politeness & provenance
- Respect robots/usage policies; default conservative rate limits.
- Identify User-Agent as SensibLaw.
- Cache locally to avoid repeated fetches where possible.
- Provenance (source, url/path, status_code, content_type) may be stored; keep timestamps outside identity hashes.

### AustLII access notes
- SINO CGI endpoints return HTTP 410 to generic/bot User-Agents.
- SensibLaw intentionally uses a browser-like User-Agent and Referer for the public search interface.
- Searches remain rate-limited, citation-driven, and depth/volume bounded; no crawling.
- CI uses saved HTML fixtures; live access is opt-in only.

## Forbidden language
Adapters do **not** perform forbidden-language scanning; that applies to exports/UI/tests, not raw fetches.

## Determinism
- No timestamps in emitted payloads that would affect hashing.
- Repeated searches with same parameters must produce identical request URLs.
