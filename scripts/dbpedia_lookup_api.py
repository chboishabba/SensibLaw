#!/usr/bin/env python3
"""DBpedia Lookup API helper (curation-time; not a runtime dependency).

DBpedia's public SPARQL endpoint can be slow/flaky. The Lookup service is a
lighter-weight way to resolve a string -> candidate DBpedia resource URIs.

Official docs:
- https://www.dbpedia.org/resources/lookup/

This script:
- queries the Lookup API
- caches results locally under `SensibLaw/.cache_local/` (gitignored)
- prints normalized JSON for review/curation
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional


DEFAULT_BASE_URL = "http://lookup.dbpedia.org/api/search"

_TAG_RE = re.compile(r"<[^>]+>")


def _clean_markup(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = html.unescape(str(value))
    text = _TAG_RE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


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


def _get_json(url: str, *, timeout_s: int) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "itir-suite/dbpedia-lookup-api (curation-time)",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    return json.loads(body)


def _normalize_results(payload: dict) -> List[Dict[str, Any]]:
    # Lookup returns a JSON object with `docs` (Lucene-ish) in most configs.
    docs = payload.get("docs")
    if not isinstance(docs, list):
        return []
    rows: List[Dict[str, Any]] = []
    for doc in docs:
        if not isinstance(doc, dict):
            continue
        uri = doc.get("resource") or doc.get("uri") or doc.get("id")
        if isinstance(uri, list):
            uri = uri[0] if uri else None
        if not uri:
            continue
        label = doc.get("label")
        if isinstance(label, list):
            label = label[0] if label else None
        label_html = str(label) if label is not None else None
        label_clean = _clean_markup(label_html)
        comment = doc.get("comment") or doc.get("description") or doc.get("abstract")
        if isinstance(comment, list):
            comment = comment[0] if comment else None
        comment_html = str(comment) if comment is not None else None
        comment_clean = _clean_markup(comment_html)
        types = doc.get("type") or doc.get("types")
        if types is None:
            types_list: List[str] = []
        elif isinstance(types, list):
            types_list = [str(t) for t in types if t]
        else:
            types_list = [str(types)]
        rows.append(
            {
                "uri": str(uri),
                "label": label_clean,
                "label_html": label_html if label_html != label_clean else None,
                "comment": comment_clean,
                "comment_html": comment_html if comment_html != comment_clean else None,
                "types": types_list,
            }
        )
    return rows


def _dbpedia_external_url(uri: str) -> str:
    # DBpedia "resource" URIs are fine to click. Keep it simple and stable.
    return uri


def _build_notes(term: str, row: Mapping[str, Any], *, picked_index: int, total: int) -> str:
    label = row.get("label")
    types = row.get("types") or []
    types_str = ", ".join(str(t) for t in types) if types else "none"
    comment = row.get("comment")
    comment_snip = None
    if comment:
        comment_snip = str(comment)
        if len(comment_snip) > 240:
            comment_snip = comment_snip[:240] + "..."
    parts = [
        "curation=UNREVIEWED",
        "source=dbpedia_lookup_api",
        f"term={term!r}",
        f"pick={picked_index}/{total}",
    ]
    if label:
        parts.append(f"label={str(label)!r}")
    parts.append(f"types={types_str}")
    if comment_snip:
        parts.append(f"comment={comment_snip!r}")
    return "; ".join(parts)


def _external_refs_batch_payload(
    *,
    term: str,
    url: str,
    rows: List[Dict[str, Any]],
    pick: Optional[int],
    actor_id: Optional[int],
    concept_code: Optional[str],
) -> dict:
    """Emit a curated batch skeleton compatible with `ontology external-refs-upsert`.

    We keep extra context under `meta` (ignored by the upsert CLI) so the batch
    remains reviewable without reaching back to DBpedia.
    """

    total = len(rows)
    picked_row: Optional[Dict[str, Any]] = None
    if pick is not None:
        if pick < 1 or pick > total:
            raise ValueError(f"--pick must be between 1 and {total} (got {pick})")
        picked_row = rows[pick - 1]

    actor_external_refs: List[dict] = []
    concept_external_refs: List[dict] = []

    if picked_row is not None:
        uri = picked_row.get("uri")
        if uri:
            if actor_id is not None:
                actor_external_refs.append(
                    {
                        "actor_id": int(actor_id),
                        "provider": "dbpedia",
                        "external_id": str(uri),
                        "external_url": _dbpedia_external_url(str(uri)),
                        "notes": _build_notes(term, picked_row, picked_index=pick or 1, total=total),
                    }
                )
            if concept_code:
                concept_external_refs.append(
                    {
                        "concept_code": str(concept_code),
                        "provider": "dbpedia",
                        "external_id": str(uri),
                        "external_url": _dbpedia_external_url(str(uri)),
                        "notes": _build_notes(term, picked_row, picked_index=pick or 1, total=total),
                    }
                )

    return {
        "meta": {
            "provider": "dbpedia",
            "service": "lookup",
            "term": term,
            "url": url,
            "rows": rows,
            "pick": pick,
            "actor_id": actor_id,
            "concept_code": concept_code,
            "curation_hint": (
                "Re-run with --pick N plus --actor-id or --concept-code to emit an actionable row; "
                "otherwise manually copy the chosen uri into actor_external_refs / concept_external_refs."
            ),
        },
        "concept_external_refs": concept_external_refs,
        "actor_external_refs": actor_external_refs,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="DBpedia Lookup API search (string -> candidate URIs).")
    ap.add_argument("term", help="Search term (e.g. 'Westmead Hospital')")
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"Lookup base URL (default: {DEFAULT_BASE_URL})")
    ap.add_argument("--max-results", type=int, default=25, help="Max results (default: 25)")
    ap.add_argument("--type", default=None, help="Optional DBpedia class/type filter (service-dependent)")
    ap.add_argument("--timeout", type=int, default=20, help="HTTP timeout seconds (default: 20)")
    ap.add_argument(
        "--cache-dir",
        default=str(Path("SensibLaw/.cache_local/dbpedia_lookup").as_posix()),
        help="Cache directory (default: SensibLaw/.cache_local/dbpedia_lookup)",
    )
    ap.add_argument(
        "--cache-max-age-s",
        type=int,
        default=7 * 24 * 3600,
        help="Cache max age seconds; 0 disables expiry (default: 7 days)",
    )
    ap.add_argument("--no-cache", action="store_true", help="Disable cache reads/writes")
    ap.add_argument("--raw", action="store_true", help="Include raw API response in output")
    ap.add_argument(
        "--emit-batch",
        type=Path,
        default=None,
        help=(
            "Write a curated batch skeleton (compatible with `ontology external-refs-upsert`) to this path. "
            "Recommended: SensibLaw/.cache_local/external_refs_<name>.json"
        ),
    )
    ap.add_argument("--pick", type=int, default=None, help="1-based candidate row index to emit into the batch")
    ap.add_argument("--actor-id", type=int, default=None, help="Actor ID to anchor emitted actor_external_refs row")
    ap.add_argument("--concept-code", default=None, help="Concept code to anchor emitted concept_external_refs row")
    args = ap.parse_args()

    params = {"format": "JSON", "query": args.term, "maxResults": str(args.max_results)}
    if args.type:
        params["type"] = args.type
    url = f"{args.base_url}?{urllib.parse.urlencode(params)}"

    cache_key = _sha256_text(url)
    cache_dir = Path(args.cache_dir)
    if not args.no_cache:
        cached = _read_cache(cache_dir, cache_key, max_age_s=max(0, args.cache_max_age_s))
        if cached is not None:
            print(json.dumps(cached, indent=2, sort_keys=True))
            return 0

    try:
        raw = _get_json(url, timeout_s=args.timeout)
    except Exception as exc:
        print(f"error: dbpedia lookup api failed: {exc}", file=sys.stderr)
        print("hint: network/DNS must allow outbound access to lookup.dbpedia.org", file=sys.stderr)
        return 2

    rows = _normalize_results(raw)
    out: dict = {
        "provider": "dbpedia",
        "service": "lookup",
        "url": url,
        "rows": rows,
    }
    if args.raw:
        out["raw"] = raw

    if not args.no_cache:
        try:
            _write_cache(cache_dir, cache_key, out)
        except Exception:
            pass

    if args.emit_batch is not None:
        try:
            batch = _external_refs_batch_payload(
                term=args.term,
                url=url,
                rows=rows,
                pick=args.pick,
                actor_id=args.actor_id,
                concept_code=args.concept_code,
            )
        except Exception as exc:
            print(f"error: unable to build batch payload: {exc}", file=sys.stderr)
            return 2

        try:
            args.emit_batch.parent.mkdir(parents=True, exist_ok=True)
            args.emit_batch.write_text(json.dumps(batch, indent=2, sort_keys=True), encoding="utf-8")
        except Exception as exc:
            print(f"error: unable to write --emit-batch file: {exc}", file=sys.stderr)
            return 2

    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
