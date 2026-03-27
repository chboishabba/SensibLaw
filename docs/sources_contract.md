# Sources Contract (Search vs Fetch)

## Core rule
**Search adapters return references; fetch adapters return bytes.**  
No adapter tokenises, parses, deduplicates, or infers. Semantics begin only after ingestion.

## Adapters

- **AustLII SINO (search)**  
  - API: `search(query, meta/vc, method, results, offset, mask_path|mask_phc)`  
  - Returns: list of `{title, url, citation?, database_heading?}`  
  - Deterministic URL builder, polite rate limit (default 0.25 rps, burst 1).
  - No crawling or pagination beyond explicit `offset + results`.

- **AustLII fetch (document)**  
  - Input: explicit AustLII URL (HTML/PDF).  
  - Returns: raw bytes + provenance (url, path, content_type, status_code).  
  - Rejects non-AustLII URLs. Default 0.25 rps.
  - For case authorities, the repo may deterministically derive the canonical
    AustLII case URL from a neutral citation before fetch. This is treated as
    an explicit fetch target, not a live search.

- **JADE fetch (document)**  
  - Input: citation or constructed URL.  
  - Returns: raw bytes + provenance.  
  - No API key assumed; semantic-free.

- **JADE search (best-effort reference selection)**  
  - Input: bounded free-text query against the public `/search/{term}` route.  
  - Returns: references only; server-rendered hit parsing is best-effort.  
  - When the query contains a neutral citation, operator tooling may append a
    deterministic `/mnc/...` fallback hit locally rather than polling again.
  - Local `results` / `offset` windows are applied after parsing because the
    public search shell does not expose a stable documented paging contract.

## Known-authority retrieval (operator workflow)
- For a known case or neutral citation, stay inside repo-owned seams.
- Preferred resolution order for operator use:
  already-ingested/local artifact → explicit AustLII URL if known →
  JADE exact MNC when authorized → deterministic `MNC -> AustLII case URL`
  derivation → AustLII SINO search → unresolved.
- Deterministic `MNC -> AustLII case URL` derivation is an approved repo-owned
  operator step for known case citations. It is a direct URL-construction path,
  not a heuristic web probe and not a generic search.
- JADE known-authority retrieval should use the repo-owned fetch seam with a
  neutral citation or explicit JADE URL, then perform paragraph/location
  isolation locally on the fetched artifact.
- AustLII known-authority retrieval should support either an explicit AustLII
  case URL or a neutral citation that is deterministically resolved to the
  canonical AustLII case URL before fetch, then perform paragraph/location
  isolation locally on the fetched artifact.
- `sensiblaw jade-search` is allowed as a secondary operator seam when a user
  starts from free text or when the query itself contains the neutral citation;
  exact `jade-fetch` remains the stable recommended core.
- Use search only to select a concrete authority URL; once bytes are fetched,
  paragraph/location isolation should happen locally against the fetched
  artifact or persisted document, not through repeated live queries.
- Optional persisted bounded ingest is now allowed for operator-selected
  authorities:
  `sensiblaw austlii-search --db-path ...` and
  `sensiblaw jade-fetch --db-path ...` and
  `sensiblaw jade-search --db-path ...` persist a canonical sqlite receipt with
  whole-fetch provenance plus bounded selected paragraph segments.
- Normal AU semantic/fact-review runtime may reuse those persisted receipts as
  a read-only authority-context lane. The intended ordering is:
  cite-like text/hint -> persisted authority receipt -> lightweight authority
  substrate summary -> optional deeper bounded follow if a concrete unresolved
  conjecture remains.
- Reusing persisted receipts is allowed as default context because it does not
  perform live network follow. Parser-seen cite-like text alone must still not
  trigger fetch/follow/ingest.
- If raw artifacts and JSON receipts are needed for case prep, write the
  fetched bytes under `demo/ingest/authority_checks/` and export the receipt
  from `scripts/query_fact_review.py authority-summary` instead of scraping
  mixed CLI stdout.
- This receiver is operator-ingest only. It does not auto-wire authority
  follow into the AU semantic/fact-review runtime.
- Do not use generic search engines, ad hoc `curl`/`requests` probes, or
  repeated site polling outside the documented adapters/scripts.

## Citation-following (bounded)
- Expansion is **citation-driven**, not crawling.
- Bounds required: `max_depth` and `max_new_docs` (both must be set).
- Resolution order: already-ingested → local PDF → JADE (exact MNC) →
  AustLII (explicit URL or deterministic case-URL derivation) →
  AustLII search → unresolved.
- Provenance recorded (source, citation, citing_doc) but kept out of identity hashes.

## Politeness & provenance
- Respect robots/usage policies; default conservative rate limits.
- Identify User-Agent as SensibLaw.
- Cache locally to avoid repeated fetches where possible.
- Provenance (source, url/path, status_code, content_type) may be stored; keep timestamps outside identity hashes.

### Implemented pacing defaults (current scripts)
- `scripts/source_pack_manifest_pull.py`
  - `--legal-rps 0.25` (4 seconds between legal-host requests)
  - `--wiki-rps 1.0` (1 second between wiki-host requests)
  - `--default-rps 0.5` (2 seconds between other hosts)
- `scripts/source_pack_authority_follow.py`
  - same defaults as above; per-host-bucket pacing applied before each fetch
- `scripts/wiki_pull_api.py`
  - `--wiki-rps 1.0` pacing for MediaWiki API/category requests

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
