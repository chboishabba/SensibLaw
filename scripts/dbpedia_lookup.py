#!/usr/bin/env python3
"""DBpedia SPARQL lookup helper (curation-time; not a runtime dependency).

This is intentionally small and boring:
- query DBpedia's SPARQL endpoint for candidate URIs by label
- optionally cache responses locally (gitignored)
- emit JSON suitable for manual review/curation

It does not attempt to "import DBpedia" into our ontology. It is a candidate
generator for creating `concept_external_refs` / `actor_external_refs` batches.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional


# DBpedia docs still publish the SPARQL endpoint as http. Also, nginx caching is keyed
# on the query string; using GET tends to behave better than POST in practice.
DEFAULT_ENDPOINT = "http://dbpedia.org/sparql"


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read_cache(cache_dir: Path, key: str, *, max_age_s: int) -> Optional[dict]:
    path = cache_dir / f"{key}.json"
    if not path.exists():
        return None
    if max_age_s > 0:
        age = time.time() - path.stat().st_mtime
        if age > max_age_s:
            return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_cache(cache_dir: Path, key: str, payload: dict) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{key}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _sparql_label_lookup(
    *,
    term: str,
    limit: int,
    type_uri: Optional[str] = None,
    include_abstract: bool = False,
    include_type: bool = False,
) -> str:
    # Note: DBpedia uses standard prefixes; we keep this query conservative.
    # We do not follow redirects here; curation can handle that explicitly.
    term_lc = term.strip().lower().replace('"', '\\"')
    type_triple = ""
    if type_uri:
        type_triple = f"  ?item a <{type_uri}> .\n"
    select_vars = ["?item", "?label"]
    optional_blocks: list[str] = []
    if include_abstract:
        select_vars.append("?abstract")
        optional_blocks.append(
            """
  OPTIONAL {
    ?item dbo:abstract ?abstract .
    FILTER (lang(?abstract) = "en") .
  }
""".rstrip()
        )
    if include_type:
        select_vars.append("?type")
        optional_blocks.append(
            """
  OPTIONAL {
    ?item rdf:type ?type .
    FILTER (STRSTARTS(STR(?type), "http://dbpedia.org/ontology/")) .
  }
""".rstrip()
        )

    optional = "\n".join(optional_blocks)
    return f"""
PREFIX dbo: <http://dbpedia.org/ontology/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT {' '.join(select_vars)} WHERE {{
{type_triple}  ?item rdfs:label ?label .
  FILTER (lang(?label) = "en") .
  FILTER (CONTAINS(LCASE(STR(?label)), "{term_lc}")) .
{optional}
}}
LIMIT {int(limit)}
""".strip()


def _get_sparql_json(endpoint: str, query: str, *, timeout_s: int) -> dict:
    url = f"{endpoint}?{urllib.parse.urlencode({'query': query})}"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/sparql-results+json",
            "User-Agent": "itir-suite/dbpedia-lookup (curation-time)",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    return json.loads(body)


def _post_sparql_json(endpoint: str, query: str, *, timeout_s: int) -> dict:
    data = urllib.parse.urlencode({"query": query}).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=data,
        headers={
            "Accept": "application/sparql-results+json",
            "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
            "User-Agent": "itir-suite/dbpedia-lookup (curation-time)",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    return json.loads(body)


def _bindings_to_rows(payload: dict) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    bindings = (payload.get("results") or {}).get("bindings") or []
    for b in bindings:
        item = (b.get("item") or {}).get("value")
        if not item:
            continue
        rows.append(
            {
                "uri": item,
                "label": (b.get("label") or {}).get("value"),
                "abstract": (b.get("abstract") or {}).get("value"),
                "type": (b.get("type") or {}).get("value"),
            }
        )
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description="Lookup DBpedia URIs via SPARQL label search.")
    ap.add_argument("term", help="Search term (matched as case-insensitive substring of rdfs:label)")
    ap.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help=f"SPARQL endpoint (default: {DEFAULT_ENDPOINT})")
    ap.add_argument(
        "--method",
        default="get",
        choices=("get", "post"),
        help="HTTP method (default: get). GET tends to benefit from endpoint caching.",
    )
    ap.add_argument("--limit", type=int, default=25, help="Max rows (default: 25)")
    ap.add_argument(
        "--type-uri",
        default=None,
        help="Optional rdf:type URI filter (e.g. http://dbpedia.org/ontology/Hospital)",
    )
    ap.add_argument("--with-abstract", action="store_true", help="Include dbo:abstract in results (slower)")
    ap.add_argument("--with-type", action="store_true", help="Include rdf:type in results (slower)")
    ap.add_argument("--timeout", type=int, default=30, help="HTTP timeout seconds (default: 30)")
    ap.add_argument(
        "--cache-dir",
        default=str(Path("SensibLaw/.cache_local/dbpedia").as_posix()),
        help="Cache directory (default: SensibLaw/.cache_local/dbpedia)",
    )
    ap.add_argument(
        "--cache-max-age-s",
        type=int,
        default=7 * 24 * 3600,
        help="Cache max age seconds; 0 disables expiry (default: 7 days)",
    )
    ap.add_argument("--no-cache", action="store_true", help="Disable cache reads/writes")
    ap.add_argument("--raw", action="store_true", help="Print raw SPARQL JSON response")
    args = ap.parse_args()

    query = _sparql_label_lookup(
        term=args.term,
        limit=args.limit,
        type_uri=args.type_uri,
        include_abstract=args.with_abstract,
        include_type=args.with_type,
    )
    cache_key = _sha256_text("\n".join([args.endpoint.strip(), query]))
    cache_dir = Path(args.cache_dir)

    if not args.no_cache:
        cached = _read_cache(cache_dir, cache_key, max_age_s=max(0, args.cache_max_age_s))
        if cached is not None:
            print(json.dumps(cached, indent=2, sort_keys=True))
            return 0

    try:
        if args.method == "post":
            raw = _post_sparql_json(args.endpoint, query, timeout_s=args.timeout)
        else:
            raw = _get_sparql_json(args.endpoint, query, timeout_s=args.timeout)
    except Exception as exc:
        print(f"error: dbpedia lookup failed: {exc}", file=sys.stderr)
        print("hint: network/DNS must allow outbound access to dbpedia.org", file=sys.stderr)
        return 2

    out: dict = {
        "provider": "dbpedia",
        "endpoint": args.endpoint,
        "query": query,
        "rows": _bindings_to_rows(raw),
    }
    if args.raw:
        out["raw"] = raw

    if not args.no_cache:
        try:
            _write_cache(cache_dir, cache_key, out)
        except Exception:
            # Cache should never be a hard failure.
            pass

    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
