#!/usr/bin/env python3
"""Fetch revision-locked random Wikipedia page samples into a replayable manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

_THIS_DIR = Path(__file__).resolve().parent
_SENSIBLAW_ROOT = _THIS_DIR.parent
if str(_SENSIBLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(_SENSIBLAW_ROOT))

from scripts import wiki_pull_api  # noqa: E402


SCHEMA_VERSION = "wiki_random_page_sample_manifest_v0_1"


def _fetch_random_titles(
    *,
    wiki: str,
    count: int,
    namespace: int,
    timeout_s: int,
    pacer: Optional[wiki_pull_api._RequestPacer],
) -> list[str]:
    if wiki not in wiki_pull_api.WIKIS:
        raise SystemExit(f"unknown wiki '{wiki}' (choices: {', '.join(sorted(wiki_pull_api.WIKIS))})")
    url = wiki_pull_api._build_url(
        wiki_pull_api.WIKIS[wiki],
        {
            "action": "query",
            "format": "json",
            "formatversion": 2,
            "list": "random",
            "rnlimit": max(1, min(int(count), 500)),
            "rnnamespace": int(namespace),
        },
    )
    payload = wiki_pull_api._get_json(url, timeout_s=timeout_s, pacer=pacer)
    rows = (payload.get("query") or {}).get("random") or []
    titles: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        title = row.get("title")
        if isinstance(title, str) and title.strip():
            titles.append(title.strip())
    return titles


def build_random_sample_manifest(
    *,
    wiki: str,
    count: int,
    namespace: int,
    out_dir: Path,
    timeout_s: int,
    wiki_rps: float,
    max_links: int,
    max_categories: int,
    include_wikitext: bool,
    follow_hops: int = 1,
    max_follow_links_per_page: int = 5,
) -> dict[str, Any]:
    pacer = wiki_pull_api._RequestPacer(wiki_rps=max(0.01, float(wiki_rps)))
    titles = _fetch_random_titles(
        wiki=wiki,
        count=count,
        namespace=namespace,
        timeout_s=timeout_s,
        pacer=pacer,
    )
    sample_rows: list[dict[str, Any]] = []
    for title in titles:
        snapshot = wiki_pull_api._fetch_latest_wikitext(
            wiki=wiki,
            title=title,
            max_links=max_links,
            max_categories=max_categories,
            include_wikitext=include_wikitext,
            timeout_s=timeout_s,
            pacer=pacer,
        )
        snapshot_path = wiki_pull_api._write_snapshot(out_dir, snapshot)
        followed_rows: list[dict[str, Any]] = []
        if int(follow_hops) > 0:
            seen_follow_titles: set[str] = set()
            for follow_title in list(snapshot.links or [])[: max(0, int(max_follow_links_per_page))]:
                follow_title = str(follow_title or "").strip()
                if not follow_title or follow_title == snapshot.title or follow_title in seen_follow_titles:
                    continue
                seen_follow_titles.add(follow_title)
                followed = wiki_pull_api._fetch_latest_wikitext(
                    wiki=wiki,
                    title=follow_title,
                    max_links=max_links,
                    max_categories=max_categories,
                    include_wikitext=include_wikitext,
                    timeout_s=timeout_s,
                    pacer=pacer,
                )
                followed_path = wiki_pull_api._write_snapshot(out_dir, followed)
                followed_rows.append(
                    {
                        "title": followed.title,
                        "pageid": followed.pageid,
                        "revid": followed.revid,
                        "source_url": followed.source_url,
                        "snapshot_path": str(followed_path),
                        "parent_title": snapshot.title,
                        "parent_revid": snapshot.revid,
                        "warning_count": len(followed.warnings),
                        "warnings": list(followed.warnings),
                    }
                )
        sample_rows.append(
            {
                "title": snapshot.title,
                "pageid": snapshot.pageid,
                "revid": snapshot.revid,
                "source_url": snapshot.source_url,
                "snapshot_path": str(snapshot_path),
                "link_count": len(snapshot.links),
                "category_count": len(snapshot.categories),
                "warning_count": len(snapshot.warnings),
                "warnings": list(snapshot.warnings),
                "followed_snapshot_count": len(followed_rows),
                "followed_samples": followed_rows,
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "wiki": wiki,
        "requested_count": int(count),
        "sampled_count": len(sample_rows),
        "namespace": int(namespace),
        "include_wikitext": bool(include_wikitext),
        "wiki_rps": float(wiki_rps),
        "follow_hops": max(0, int(follow_hops)),
        "max_follow_links_per_page": max(0, int(max_follow_links_per_page)),
        "generated_at": wiki_pull_api._utc_iso(),
        "samples": sample_rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch random Wikipedia pages into a replayable snapshot manifest.")
    parser.add_argument("--wiki", default="enwiki", choices=sorted(wiki_pull_api.WIKIS.keys()))
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--namespace", type=int, default=0)
    parser.add_argument("--out-dir", type=Path, default=Path("SensibLaw/.cache_local/wiki_random_page_samples"))
    parser.add_argument("--out-manifest", type=Path, required=True)
    parser.add_argument("--max-links", type=int, default=50)
    parser.add_argument("--max-categories", type=int, default=50)
    parser.add_argument("--follow-hops", type=int, default=1)
    parser.add_argument("--max-follow-links-per-page", type=int, default=5)
    parser.add_argument("--timeout-s", type=int, default=30)
    parser.add_argument("--wiki-rps", type=float, default=1.0)
    parser.add_argument("--no-wikitext", action="store_true")
    args = parser.parse_args(argv)

    manifest = build_random_sample_manifest(
        wiki=args.wiki,
        count=args.count,
        namespace=args.namespace,
        out_dir=args.out_dir,
        timeout_s=args.timeout_s,
        wiki_rps=args.wiki_rps,
        max_links=args.max_links,
        max_categories=args.max_categories,
        include_wikitext=not args.no_wikitext,
        follow_hops=args.follow_hops,
        max_follow_links_per_page=args.max_follow_links_per_page,
    )
    args.out_manifest.parent.mkdir(parents=True, exist_ok=True)
    args.out_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
