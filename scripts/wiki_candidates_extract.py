#!/usr/bin/env python3
"""Extract candidate entities (actors/concepts) from Wikipedia snapshot JSONs.

This is a curation-time helper:
- input: snapshot JSONs produced by `SensibLaw/scripts/wiki_pull_api.py`
- output: a ranked list of linked titles + categories + provenance per title

It does NOT upsert into ontology DB automatically. It emits a reviewable JSON
payload that can be used to decide:
- which titles should be treated as actor candidates vs concept candidates
- which titles should be sent through DBpedia lookup for external ID anchoring

Design intent:
- keep the pipeline deterministic and offline once snapshots exist
- avoid "crawl the world": we only use what the snapshot already captured
"""

from __future__ import annotations

import argparse
import glob
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


DEFAULT_EXCLUDE_TITLE_PREFIXES = (
    "Category:",
    "File:",
    "Help:",
    "Portal:",
    "Special:",
    "Template:",
    "Wikipedia:",
    "Talk:",
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _iter_snapshot_paths(inputs: List[str]) -> Iterable[Path]:
    for pattern in inputs:
        for raw in glob.glob(pattern):
            p = Path(raw)
            if p.is_file() and p.suffix.lower() == ".json":
                yield p


def _is_excluded_title(title: str, prefixes: Tuple[str, ...]) -> bool:
    t = title.strip()
    if not t:
        return True
    return any(t.startswith(p) for p in prefixes)


@dataclass(frozen=True)
class Evidence:
    source_path: str
    wiki: str
    page_title: str
    page_revid: Optional[int]
    source_url: str


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Extract ranked candidate titles from wiki snapshot JSONs.")
    ap.add_argument(
        "--in",
        dest="inputs",
        action="append",
        default=[],
        help=(
            "Input file glob (repeatable). Example: "
            "'SensibLaw/.cache_local/wiki_snapshots/*.json'"
        ),
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=Path("SensibLaw/.cache_local/wiki_candidates_gwb.json"),
        help="Output JSON path (gitignored by SensibLaw/.gitignore).",
    )
    ap.add_argument("--min-count", type=int, default=1, help="Only keep titles seen >= N times.")
    ap.add_argument("--limit", type=int, default=250, help="Max titles to emit (after ranking).")
    ap.add_argument(
        "--exclude-prefix",
        action="append",
        default=list(DEFAULT_EXCLUDE_TITLE_PREFIXES),
        help="Exclude titles with this prefix (repeatable).",
    )
    ap.add_argument(
        "--include-categories",
        action="store_true",
        help="Include snapshot categories as candidates (lower weight than links).",
    )
    args = ap.parse_args(argv)

    if not args.inputs:
        raise SystemExit("no inputs (use --in with a glob path)")

    exclude_prefixes = tuple(p for p in (args.exclude_prefix or []) if p)

    title_counts = Counter()
    title_sources: Dict[str, List[Evidence]] = defaultdict(list)

    for path in _iter_snapshot_paths(args.inputs):
        snap = _load_json(path)
        wiki = str(snap.get("wiki") or "")
        page_title = str(snap.get("title") or "")
        page_revid = snap.get("revid")
        try:
            page_revid_int = int(page_revid) if page_revid is not None else None
        except Exception:
            page_revid_int = None
        source_url = str(snap.get("source_url") or "")

        ev = Evidence(
            source_path=str(path),
            wiki=wiki,
            page_title=page_title,
            page_revid=page_revid_int,
            source_url=source_url,
        )

        links = snap.get("links") or []
        if isinstance(links, list):
            for t in links:
                if not isinstance(t, str):
                    continue
                title = t.strip()
                if _is_excluded_title(title, exclude_prefixes):
                    continue
                title_counts[title] += 3  # links are higher-signal than categories
                title_sources[title].append(ev)

        if args.include_categories:
            cats = snap.get("categories") or []
            if isinstance(cats, list):
                for t in cats:
                    if not isinstance(t, str):
                        continue
                    title = t.strip()
                    if _is_excluded_title(title, exclude_prefixes):
                        continue
                    title_counts[title] += 1
                    title_sources[title].append(ev)

    min_count = max(1, int(args.min_count))
    limit = max(1, int(args.limit))

    rows: List[Dict[str, Any]] = []
    for title, score in title_counts.most_common():
        if score < min_count:
            continue
        srcs = title_sources.get(title) or []
        # De-dupe evidence by page+revid to keep payload size bounded.
        uniq = {}
        for ev in srcs:
            key = (ev.wiki, ev.page_title, ev.page_revid, ev.source_url)
            uniq[key] = ev
        evidence = [
            {
                "wiki": ev.wiki,
                "page_title": ev.page_title,
                "page_revid": ev.page_revid,
                "source_url": ev.source_url,
                "source_path": ev.source_path,
            }
            for ev in uniq.values()
        ]
        rows.append(
            {
                "title": title,
                "score": int(score),
                "evidence": evidence[:20],
            }
        )
        if len(rows) >= limit:
            break

    out = {
        "ok": True,
        "inputs": list(args.inputs),
        "exclude_prefixes": list(exclude_prefixes),
        "min_count": min_count,
        "limit": limit,
        "rows": rows,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(args.out), "row_count": len(rows)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

