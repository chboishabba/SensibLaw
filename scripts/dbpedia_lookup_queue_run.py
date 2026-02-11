#!/usr/bin/env python3
"""Run DBpedia lookup for a bounded queue and annotate results.

This is a curation-time helper:
- input: `SensibLaw/.cache_local/dbpedia_lookup_queue_*.json` (gitignored)
- output: updated queue JSON (same shape) with:
  - `dbpedia_candidates` attached (optional, capped)
  - `status` updated to `pending|ambiguous|skipped`

Important: this script does not choose a DBpedia URI automatically.
DBpedia resolution is identity glue, not evidence, and does not imply inclusion
in any investigative graph.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _lookup_api(
    *,
    term: str,
    type_filter: Optional[str],
    timeout_s: int,
    cache_dir: Path,
    cache_max_age_s: int,
    allow_network: bool,
) -> dict:
    # Import the helper to reuse cache + normalization behavior.
    # Ensure this script works from any CWD (not just `SensibLaw/scripts`).
    import sys

    script_dir = str(Path(__file__).resolve().parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    import dbpedia_lookup_api as api  # type: ignore

    params = {"format": "JSON", "query": term, "maxResults": "25"}
    if type_filter:
        params["type"] = type_filter
    url = f"{api.DEFAULT_BASE_URL}?{api.urllib.parse.urlencode(params)}"  # type: ignore[attr-defined]
    cache_key = api._sha256_text(url)  # type: ignore[attr-defined]

    if not allow_network:
        cached = api._read_cache(cache_dir, cache_key, max_age_s=max(0, cache_max_age_s))  # type: ignore[attr-defined]
        if cached is None:
            return {"ok": False, "error": "cache_miss_network_disallowed", "rows": []}
        return {"ok": True, "rows": cached.get("rows") or [], "cached": True}

    # Try cache first, then network.
    cached = api._read_cache(cache_dir, cache_key, max_age_s=max(0, cache_max_age_s))  # type: ignore[attr-defined]
    if cached is not None:
        return {"ok": True, "rows": cached.get("rows") or [], "cached": True}

    try:
        raw = api._get_json(url, timeout_s=timeout_s)  # type: ignore[attr-defined]
        rows = api._normalize_results(raw)  # type: ignore[attr-defined]
        out = {"provider": "dbpedia", "service": "lookup", "url": url, "rows": rows}
        try:
            api._write_cache(cache_dir, cache_key, out)  # type: ignore[attr-defined]
        except Exception:
            pass
        return {"ok": True, "rows": rows, "cached": False}
    except Exception as exc:
        return {"ok": False, "error": f"network_error:{exc}", "rows": []}


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Annotate a DBpedia lookup queue by running lookup.dbpedia.org.")
    ap.add_argument(
        "--in",
        dest="in_path",
        type=Path,
        default=Path("SensibLaw/.cache_local/dbpedia_lookup_queue_gwb.json"),
        help="Input queue JSON (default: %(default)s)",
    )
    ap.add_argument(
        "--out",
        dest="out_path",
        type=Path,
        default=Path("SensibLaw/.cache_local/dbpedia_lookup_queue_gwb.annotated.json"),
        help="Output annotated queue JSON (default: %(default)s)",
    )
    ap.add_argument("--timeout-s", type=int, default=20, help="HTTP timeout seconds (default: 20)")
    ap.add_argument("--cache-max-age-s", type=int, default=7 * 24 * 3600, help="Cache max age seconds (default: 7d)")
    ap.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("SensibLaw/.cache_local/dbpedia_lookup"),
        help="Cache directory (default: SensibLaw/.cache_local/dbpedia_lookup)",
    )
    ap.add_argument(
        "--allow-network",
        action="store_true",
        help="Allow network fetches on cache misses (default: cache-only).",
    )
    ap.add_argument(
        "--type",
        dest="type_filter",
        default=None,
        help="Optional DBpedia class/type filter passed to the Lookup service (reduces junk candidates).",
    )
    ap.add_argument("--max-items", type=int, default=50, help="Max queue items to process (default: 50)")
    ap.add_argument("--max-candidates", type=int, default=8, help="Max DBpedia candidates stored per title (default: 8)")
    args = ap.parse_args(argv)

    q = _load_json(args.in_path)
    candidates = q.get("candidates") or []
    if not isinstance(candidates, list):
        raise SystemExit("invalid queue: candidates[] missing")

    processed = 0
    updated = 0
    started = time.monotonic()
    for item in candidates:
        if processed >= int(args.max_items):
            break
        if not isinstance(item, dict):
            continue
        if item.get("status") not in ("pending", "ambiguous", "skipped"):
            continue
        title = str(item.get("title") or "").strip()
        if not title:
            continue

        res = _lookup_api(
            term=title,
            type_filter=str(args.type_filter) if args.type_filter else None,
            timeout_s=int(args.timeout_s),
            cache_dir=Path(args.cache_dir),
            cache_max_age_s=int(args.cache_max_age_s),
            allow_network=bool(args.allow_network),
        )
        processed += 1

        rows = res.get("rows") or []
        if not isinstance(rows, list):
            rows = []

        # Store a small, reviewable candidate list.
        slim = []
        for row in rows[: max(0, int(args.max_candidates))]:
            if not isinstance(row, dict):
                continue
            slim.append(
                {
                    "uri": row.get("uri"),
                    "label": row.get("label"),
                    "comment": row.get("comment"),
                    "types": row.get("types") or [],
                }
            )

        note = item.get("notes") or ""
        if res.get("ok") is False and res.get("error") == "cache_miss_network_disallowed":
            item["dbpedia_candidates"] = slim
            item["status"] = "pending"
            item["notes"] = (note + "\n" if note else "") + "dbpedia_lookup=cache_miss_network_disallowed"
        elif res.get("ok") is False:
            # Do not silently "skip" on network failures; keep pending and annotate.
            item["status"] = "pending"
            err = str(res.get("error") or "unknown_error")
            item["notes"] = (note + "\n" if note else "") + f"dbpedia_lookup=error; {err}"
            item["dbpedia_candidates"] = slim
        elif res.get("cached") is True:
            item["dbpedia_candidates"] = slim
            item["status"] = "ambiguous" if len(slim) > 1 else ("pending" if len(slim) == 1 else "skipped")
            item["notes"] = (note + "\n" if note else "") + "dbpedia_lookup=cached"
        else:
            item["dbpedia_candidates"] = slim
            item["status"] = "ambiguous" if len(slim) > 1 else ("pending" if len(slim) == 1 else "skipped")
            item["notes"] = (note + "\n" if note else "") + "dbpedia_lookup=fetched"

        updated += 1

    q["generated_at"] = q.get("generated_at") or ""
    q["annotated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    q["annotation_policy"] = {
        "max_items": int(args.max_items),
        "max_candidates": int(args.max_candidates),
        "allow_network": bool(args.allow_network),
    }
    _write_json(args.out_path, q)
    elapsed = round(time.monotonic() - started, 3)
    print(json.dumps({"ok": True, "out": str(args.out_path), "processed": processed, "updated": updated, "duration_s": elapsed}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
