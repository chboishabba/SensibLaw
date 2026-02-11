#!/usr/bin/env python3
"""Wikipedia/MediaWiki pull helper (curation-time; revision-locked snapshots).

Why this exists:
- We want structured access (wikitext + revid + categories + links) without
  committing bulk HTML dumps to git.
- Outputs land under `SensibLaw/.cache_local/` (gitignored).
- pywikibot is preferred when available, but this script works without it by
  using the public MediaWiki API directly.

This is a pull/snapshot tool only. It does not extract claims or upsert into
ontology tables; those are separate, review-gated steps.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


WIKIS: dict[str, str] = {
    "enwiki": "https://en.wikipedia.org/w/api.php",
    "simplewiki": "https://simple.wikipedia.org/w/api.php",
}


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _utc_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _get_json(url: str, *, timeout_s: int) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "itir-suite/wiki-pull-api (curation-time)",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    return json.loads(body)


def _build_url(base: str, params: dict[str, str | int]) -> str:
    q = urllib.parse.urlencode({k: str(v) for k, v in params.items()})
    return f"{base}?{q}"


@dataclass(frozen=True)
class PageSnapshot:
    wiki: str
    title: str
    pageid: Optional[int]
    revid: Optional[int]
    rev_timestamp: Optional[str]
    source_url: str
    api_url: str
    fetched_at: str
    categories: List[str]
    links: List[str]
    wikitext: Optional[str]
    warnings: List[str]

    def to_json(self) -> dict:
        return {
            "wiki": self.wiki,
            "title": self.title,
            "pageid": self.pageid,
            "revid": self.revid,
            "rev_timestamp": self.rev_timestamp,
            "source_url": self.source_url,
            "api_url": self.api_url,
            "fetched_at": self.fetched_at,
            "categories": self.categories,
            "links": self.links,
            "wikitext": self.wikitext,
            "warnings": self.warnings,
        }


def _page_url(wiki: str, title: str) -> str:
    if wiki == "enwiki":
        host = "https://en.wikipedia.org"
    elif wiki == "simplewiki":
        host = "https://simple.wikipedia.org"
    else:
        host = "https://en.wikipedia.org"
    slug = title.replace(" ", "_")
    return f"{host}/wiki/{urllib.parse.quote(slug)}"


def _fetch_latest_wikitext(
    *,
    wiki: str,
    title: str,
    max_links: int,
    max_categories: int,
    include_wikitext: bool,
    timeout_s: int,
) -> PageSnapshot:
    if wiki not in WIKIS:
        raise SystemExit(f"unknown wiki '{wiki}' (choices: {', '.join(sorted(WIKIS))})")
    base = WIKIS[wiki]

    # We intentionally keep link/category pulls capped. Full link graphs can be
    # huge; discovery traversal is a separate opt-in step.
    params = {
        "action": "query",
        "format": "json",
        "formatversion": 2,
        "redirects": 1,
        "titles": title,
        "prop": "revisions|categories|links",
        "rvprop": "ids|timestamp|content",
        "rvslots": "main",
        "cllimit": max(1, min(int(max_categories), 500)),
        "clprop": "hidden",
        "pllimit": max(1, min(int(max_links), 500)),
        "plnamespace": 0,
    }
    url = _build_url(base, params)
    payload = _get_json(url, timeout_s=timeout_s)

    warnings: List[str] = []
    query = payload.get("query") or {}
    pages = query.get("pages") or []
    if not pages:
        warnings.append("no_pages_returned")
        return PageSnapshot(
            wiki=wiki,
            title=title,
            pageid=None,
            revid=None,
            rev_timestamp=None,
            source_url=_page_url(wiki, title),
            api_url=url,
            fetched_at=_utc_iso(),
            categories=[],
            links=[],
            wikitext=None,
            warnings=warnings,
        )

    page = pages[0] if isinstance(pages[0], dict) else {}
    actual_title = page.get("title") or title
    pageid = page.get("pageid")
    if page.get("missing"):
        warnings.append("page_missing")

    revid: Optional[int] = None
    rev_ts: Optional[str] = None
    wikitext: Optional[str] = None
    revs = page.get("revisions") or []
    if isinstance(revs, list) and revs:
        rev = revs[0] if isinstance(revs[0], dict) else {}
        revid_val = rev.get("revid")
        if isinstance(revid_val, int):
            revid = revid_val
        rev_ts_val = rev.get("timestamp")
        if isinstance(rev_ts_val, str):
            rev_ts = rev_ts_val
        if include_wikitext:
            slots = rev.get("slots") or {}
            main = slots.get("main") or {}
            content = main.get("content")
            if isinstance(content, str):
                wikitext = content
    else:
        warnings.append("no_revisions_returned")

    categories: List[str] = []
    for cat in page.get("categories") or []:
        if isinstance(cat, dict):
            t = cat.get("title")
            if isinstance(t, str):
                categories.append(t)
    links: List[str] = []
    for link in page.get("links") or []:
        if isinstance(link, dict):
            t = link.get("title")
            if isinstance(t, str):
                links.append(t)

    # Continuation is expected when caps are small. We surface it as a warning
    # so callers know they didn't pull the full lists.
    if payload.get("continue"):
        warnings.append("partial_lists_continue_present")

    return PageSnapshot(
        wiki=wiki,
        title=str(actual_title),
        pageid=int(pageid) if isinstance(pageid, int) else None,
        revid=revid,
        rev_timestamp=rev_ts,
        source_url=_page_url(wiki, str(actual_title)),
        api_url=url,
        fetched_at=_utc_iso(),
        categories=categories[: max(0, int(max_categories))],
        links=links[: max(0, int(max_links))],
        wikitext=wikitext,
        warnings=warnings,
    )


def _fetch_latest_pywikibot(
    *,
    wiki: str,
    title: str,
    max_links: int,
    max_categories: int,
    include_wikitext: bool,
) -> PageSnapshot:
    # pywikibot normally expects a user-config.py; this env var allows
    # read-only operation without it.
    import os

    os.environ.setdefault("PYWIKIBOT_NO_USER_CONFIG", "1")

    try:
        import pywikibot  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"pywikibot import failed: {exc}") from exc

    if wiki == "enwiki":
        site = pywikibot.Site("en", "wikipedia")
    elif wiki == "simplewiki":
        site = pywikibot.Site("simple", "wikipedia")
    else:
        raise ValueError(f"unknown wiki '{wiki}'")

    warnings: List[str] = []
    page = pywikibot.Page(site, title)
    try:
        page.get(get_redirect=True)
    except Exception:  # pragma: no cover
        warnings.append("page_get_failed")

    actual_title = page.title() if hasattr(page, "title") else title
    pageid = getattr(page, "pageid", None)
    revid = getattr(page, "latest_revision_id", None)
    rev_ts = None
    try:
        latest = getattr(page, "latest_revision", None)
        if latest is not None:
            ts = getattr(latest, "timestamp", None)
            if ts is not None:
                rev_ts = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
    except Exception:  # pragma: no cover
        pass

    wikitext = page.text if include_wikitext else None

    categories: List[str] = []
    try:
        for cat in page.categories():
            if len(categories) >= max_categories:
                break
            categories.append(cat.title())
    except Exception:  # pragma: no cover
        warnings.append("categories_fetch_failed")

    links: List[str] = []
    try:
        for linked in page.linkedPages():
            if len(links) >= max_links:
                break
            links.append(linked.title())
    except Exception:  # pragma: no cover
        warnings.append("links_fetch_failed")

    return PageSnapshot(
        wiki=wiki,
        title=str(actual_title),
        pageid=int(pageid) if isinstance(pageid, int) else None,
        revid=int(revid) if isinstance(revid, int) else None,
        rev_timestamp=str(rev_ts) if rev_ts else None,
        source_url=_page_url(wiki, str(actual_title)),
        api_url="pywikibot",
        fetched_at=_utc_iso(),
        categories=categories,
        links=links,
        wikitext=wikitext,
        warnings=warnings,
    )


def _fetch_category_members(
    *,
    wiki: str,
    category_title: str,
    max_members: int,
    timeout_s: int,
) -> List[str]:
    if wiki not in WIKIS:
        raise SystemExit(f"unknown wiki '{wiki}' (choices: {', '.join(sorted(WIKIS))})")
    base = WIKIS[wiki]
    members: List[str] = []
    cmcontinue: Optional[str] = None
    while True:
        params: dict[str, str | int] = {
            "action": "query",
            "format": "json",
            "formatversion": 2,
            "list": "categorymembers",
            "cmtitle": category_title,
            "cmlimit": 500,
            "cmnamespace": 0,
        }
        if cmcontinue:
            params["cmcontinue"] = cmcontinue
        url = _build_url(base, params)
        payload = _get_json(url, timeout_s=timeout_s)
        query = payload.get("query") or {}
        cms = query.get("categorymembers") or []
        for row in cms:
            if not isinstance(row, dict):
                continue
            title = row.get("title")
            if isinstance(title, str):
                members.append(title)
                if len(members) >= max_members:
                    return members[:max_members]
        cont = payload.get("continue") or {}
        nxt = cont.get("cmcontinue")
        if isinstance(nxt, str) and nxt:
            cmcontinue = nxt
            continue
        return members


def _write_snapshot(out_dir: Path, snap: PageSnapshot) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    # Stable-ish filename: title + revid (or "none").
    title_slug = snap.title.replace(" ", "_").replace("/", "_")
    revid = snap.revid if snap.revid is not None else "none"
    key = _sha256_text(f"{snap.wiki}|{snap.title}|{revid}")[:12]
    path = out_dir / f"{snap.wiki}__{title_slug}__revid_{revid}__{key}.json"
    path.write_text(json.dumps(snap.to_json(), indent=2, sort_keys=True), encoding="utf-8")
    return path


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--wiki", default="enwiki", choices=sorted(WIKIS.keys()))
    p.add_argument(
        "--driver",
        default="auto",
        choices=("auto", "api", "pywikibot"),
        help="Fetch driver: auto prefers pywikibot if importable, else MediaWiki API.",
    )
    p.add_argument("--title", action="append", default=[], help="Page title (repeatable)")
    p.add_argument("--titles-file", type=Path, help="File with one page title per line")
    p.add_argument(
        "--out-dir",
        type=Path,
        default=Path("SensibLaw/.cache_local/wiki_snapshots"),
        help="Output directory (gitignored)",
    )
    p.add_argument("--max-links", type=int, default=50)
    p.add_argument("--max-categories", type=int, default=50)
    p.add_argument("--no-wikitext", action="store_true", help="Skip wikitext body in snapshot JSON")
    p.add_argument("--timeout-s", type=int, default=30)
    p.add_argument("--category-traverse", action="store_true", help="Fetch 1-hop category member lists (capped)")
    p.add_argument("--category-max-members", type=int, default=200)
    p.add_argument(
        "--category-exclude-prefix",
        action="append",
        default=[
            # Skip common maintenance/meta categories by default. These are
            # low-signal for discovery and can be huge.
            "Category:All ",
            "Category:Wikipedia ",
            "Category:Articles ",
            "Category:Pages ",
            "Category:Use ",
            "Category:CS1",
            "Category:Webarchive",
            "Category:Harv and Sfn",
            "Category:Commons ",
        ],
        help="Exclude categories (prefix match). Repeatable.",
    )
    args = p.parse_args(argv)

    titles: List[str] = [t for t in (args.title or []) if t and t.strip()]
    if args.titles_file:
        raw = args.titles_file.read_text(encoding="utf-8").splitlines()
        titles.extend([line.strip() for line in raw if line.strip() and not line.strip().startswith("#")])
    if not titles:
        raise SystemExit("no titles provided (use --title or --titles-file)")

    include_wikitext = not args.no_wikitext
    out_paths: List[str] = []
    traverse_paths: List[str] = []
    drivers_used: List[str] = []
    python_exe = sys.executable

    for title in titles:
        use_pywikibot = False
        if args.driver in ("auto", "pywikibot"):
            try:
                import pywikibot  # noqa: F401

                use_pywikibot = True
            except Exception:
                use_pywikibot = False
                if args.driver == "pywikibot":
                    raise SystemExit("pywikibot requested but not importable in this environment")

        driver_used = "pywikibot" if use_pywikibot else "api"
        if driver_used not in drivers_used:
            drivers_used.append(driver_used)
        print(
            f"[wiki] fetch start wiki={args.wiki} title={title!r} driver={driver_used} python={python_exe}",
            file=sys.stderr,
            flush=True,
        )

        if use_pywikibot:
            snap = _fetch_latest_pywikibot(
                wiki=args.wiki,
                title=title,
                max_links=int(args.max_links),
                max_categories=int(args.max_categories),
                include_wikitext=include_wikitext,
            )
        else:
            snap = _fetch_latest_wikitext(
                wiki=args.wiki,
                title=title,
                max_links=int(args.max_links),
                max_categories=int(args.max_categories),
                include_wikitext=include_wikitext,
                timeout_s=int(args.timeout_s),
            )
        out_path = _write_snapshot(Path(args.out_dir), snap)
        out_paths.append(str(out_path))
        print(
            f"[wiki] snapshot wrote path={out_path} revid={snap.revid} warnings={len(snap.warnings)}",
            file=sys.stderr,
            flush=True,
        )

        if args.category_traverse and snap.categories:
            # This is discovery-only. We record a small manifest of category->members
            # to keep it reviewable.
            print(
                f"[wiki] category traverse start title={snap.title!r} categories={len(snap.categories)} max_members={int(args.category_max_members)}",
                file=sys.stderr,
                flush=True,
            )
            cat_map: Dict[str, List[str]] = {}
            excludes: Tuple[str, ...] = tuple(str(x) for x in (args.category_exclude_prefix or []) if x)
            for cat in snap.categories[: int(args.max_categories)]:
                if excludes and any(cat.startswith(prefix) for prefix in excludes):
                    continue
                cat_map[cat] = _fetch_category_members(
                    wiki=args.wiki,
                    category_title=cat,
                    max_members=int(args.category_max_members),
                    timeout_s=int(args.timeout_s),
                )
            traverse_payload = {
                "wiki": snap.wiki,
                "title": snap.title,
                "revid": snap.revid,
                "fetched_at": _utc_iso(),
                "category_max_members": int(args.category_max_members),
                "categories": cat_map,
            }
            traverse_path = Path(args.out_dir) / f"{snap.wiki}__{snap.title.replace(' ', '_')}__categories.json"
            traverse_path.write_text(json.dumps(traverse_payload, indent=2, sort_keys=True), encoding="utf-8")
            traverse_paths.append(str(traverse_path))
            print(
                f"[wiki] category traverse wrote path={traverse_path} categories_written={len(cat_map)}",
                file=sys.stderr,
                flush=True,
            )

    # Keep stdout machine-readable.
    print(
        json.dumps(
            {
                "ok": True,
                "wiki": args.wiki,
                "python": python_exe,
                "driver_requested": args.driver,
                "drivers_used": drivers_used,
                "snapshots": out_paths,
                "category_traversal": traverse_paths,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
