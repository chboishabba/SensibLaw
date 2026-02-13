#!/usr/bin/env python3
"""Bounded source-pack puller for legal-principles ingest bootstraps.

This is intentionally a reference fetcher, not a semantic parser:
- Fetch only explicit `seed_urls` from a source pack.
- Do not crawl discovered links.
- Emit deterministic manifests + chronology-friendly graph artifacts.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


AUTHORITY_HOST_SUFFIXES = (
    "austlii.edu.au",
    "hcourt.gov.au",
    "federalcourt.gov.au",
    "legislation.gov.au",
    "legislation.nsw.gov.au",
    "legislation.vic.gov.au",
    "legislation.qld.gov.au",
    "legislation.sa.gov.au",
    "legislation.wa.gov.au",
    "legislation.tas.gov.au",
    "legislation.act.gov.au",
    "legislation.nt.gov.au",
    "jade.io",
)


class _RequestPacer:
    def __init__(self, *, legal_rps: float, wiki_rps: float, default_rps: float) -> None:
        self._legal_interval = 1.0 / max(0.01, float(legal_rps))
        self._wiki_interval = 1.0 / max(0.01, float(wiki_rps))
        self._default_interval = 1.0 / max(0.01, float(default_rps))
        self._last_request_at: Dict[str, float] = {}

    def _bucket_for_url(self, url: str) -> str:
        h = _host(url)
        if h.endswith(("wikipedia.org", "wikimedia.org")):
            return "wiki"
        if _is_authority_host(url):
            return "legal"
        return "default"

    def _interval_for_bucket(self, bucket: str) -> float:
        if bucket == "wiki":
            return self._wiki_interval
        if bucket == "legal":
            return self._legal_interval
        return self._default_interval

    def wait_for(self, url: str) -> None:
        bucket = self._bucket_for_url(url)
        interval = self._interval_for_bucket(bucket)
        now = time.monotonic()
        last = self._last_request_at.get(bucket)
        if last is not None:
            wait_s = interval - (now - last)
            if wait_s > 0:
                time.sleep(wait_s)
        self._last_request_at[bucket] = time.monotonic()


def _utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def _slug(text: str) -> str:
    out = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in (text or "").strip())
    while "__" in out:
        out = out.replace("__", "_")
    return out.strip("._") or "artifact"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _collapse_ws(text: str) -> str:
    return " ".join((text or "").split()).strip()


def _host(url: str) -> str:
    return (urllib.parse.urlparse(url).netloc or "").lower()


def _is_authority_host(url: str) -> bool:
    h = _host(url)
    return any(h.endswith(suffix) for suffix in AUTHORITY_HOST_SUFFIXES)


class _LinkAndTitleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_title = False
        self._title_buf: List[str] = []
        self._active_href: Optional[str] = None
        self._active_text: List[str] = []
        self.links: List[Tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        t = (tag or "").lower()
        if t == "title":
            self.in_title = True
            self._title_buf.clear()
            return
        if t == "a":
            href = None
            for k, v in attrs:
                if (k or "").lower() == "href":
                    href = v
                    break
            self._active_href = href
            self._active_text = []

    def handle_endtag(self, tag: str) -> None:
        t = (tag or "").lower()
        if t == "title":
            self.in_title = False
            return
        if t == "a":
            if self._active_href:
                text = _collapse_ws("".join(self._active_text))
                self.links.append((self._active_href, text))
            self._active_href = None
            self._active_text = []

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self._title_buf.append(data)
            return
        if self._active_href is not None:
            self._active_text.append(data)

    @property
    def title(self) -> str:
        return _collapse_ws("".join(self._title_buf))


def _fetch(url: str, timeout: int, user_agent: str, pacer: Optional[_RequestPacer] = None) -> Dict[str, object]:
    if pacer is not None:
        pacer.wait_for(url)
    req = urllib.request.Request(url, headers={"User-Agent": user_agent}, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310 - bounded explicit fetch
        data = resp.read()
        final_url = str(resp.geturl() or url)
        status_code = int(getattr(resp, "status", 200))
        content_type = str(resp.headers.get("Content-Type") or "")
    return {
        "url": url,
        "final_url": final_url,
        "status_code": status_code,
        "content_type": content_type,
        "bytes": data,
    }


def _parse_html_links(content: bytes, final_url: str, max_links: int) -> Tuple[str, List[Dict[str, str]]]:
    text = content.decode("utf-8", errors="replace")
    parser = _LinkAndTitleParser()
    parser.feed(text)
    seen = set()
    out: List[Dict[str, str]] = []
    for href, anchor_text in parser.links:
        u = urllib.parse.urljoin(final_url, href)
        if not u.startswith(("http://", "https://")):
            continue
        key = (u, anchor_text)
        if key in seen:
            continue
        seen.add(key)
        out.append({"url": u, "text": anchor_text})
        if len(out) >= max_links:
            break
    return parser.title, out


def _iso_to_anchor(ts: str) -> Dict[str, object]:
    d = dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return {
        "year": int(d.year),
        "month": int(d.month),
        "day": int(d.day),
        "precision": "day",
        "text": d.strftime("%Y-%m-%d"),
        "kind": "ingest",
    }


def _timeline_graph(events: List[Dict[str, object]], pack_id: str) -> Dict[str, object]:
    nodes: List[Dict[str, object]] = []
    edges: List[Dict[str, object]] = []

    nodes.append({"id": f"pack:{pack_id}", "type": "pack", "label": pack_id})
    source_seen = set()
    time_seen = set()
    for ev in events:
        source_id = str(ev.get("source_id") or "")
        event_id = str(ev.get("event_id") or "")
        event_label = str(ev.get("text") or "")
        day = str(((ev.get("anchor") or {}) if isinstance(ev.get("anchor"), dict) else {}).get("text") or "")
        if source_id and source_id not in source_seen:
            nodes.append({"id": f"source:{source_id}", "type": "source", "label": source_id})
            edges.append({"from": f"pack:{pack_id}", "to": f"source:{source_id}", "type": "HAS_SOURCE"})
            source_seen.add(source_id)
        if day and day not in time_seen:
            nodes.append({"id": f"time:{day}", "type": "time_day", "label": day})
            time_seen.add(day)
        nodes.append({"id": f"ev:{event_id}", "type": "event", "label": event_label})
        if source_id:
            edges.append({"from": f"source:{source_id}", "to": f"ev:{event_id}", "type": "HAS_EVENT"})
        if day:
            edges.append({"from": f"time:{day}", "to": f"ev:{event_id}", "type": "TIME_BIN"})

    for i in range(len(events) - 1):
        a = str(events[i].get("event_id") or "")
        b = str(events[i + 1].get("event_id") or "")
        if a and b:
            edges.append({"from": f"ev:{a}", "to": f"ev:{b}", "type": "NEXT_CHRONO", "order": i + 1})

    return {
        "graph_id": f"source_pack_timeline_{pack_id}",
        "pack_id": pack_id,
        "generated_at": _utc_now_iso(),
        "nodes": nodes,
        "edges": edges,
    }


def _wiki_timeline_payload(events: List[Dict[str, object]], pack_id: str) -> Dict[str, object]:
    out_events = []
    for ev in events:
        out_events.append(
            {
                "event_id": ev["event_id"],
                "anchor": ev["anchor"],
                "section": ev.get("section") or "",
                "text": ev.get("text") or "",
                "links": list(ev.get("links") or []),
                "source_id": ev.get("source_id"),
                "url": ev.get("url"),
                "title": ev.get("title"),
            }
        )
    return {
        "snapshot": {
            "title": f"Source Pack {pack_id}",
            "wiki": "source_pack",
            "revid": None,
            "source_url": None,
        },
        "events": out_events,
    }


def _iter_seed_rows(pack: Dict[str, object]) -> Iterable[Tuple[Dict[str, object], str]]:
    sources = pack.get("sources") or []
    if not isinstance(sources, list):
        return []
    for source in sources:
        if not isinstance(source, dict):
            continue
        seed_urls = source.get("seed_urls") or []
        if not isinstance(seed_urls, list):
            continue
        for url in seed_urls:
            if isinstance(url, str) and url.strip():
                yield source, url.strip()


def run(
    pack_path: Path,
    out_dir: Path,
    timeout: int,
    max_links_per_doc: int,
    max_authority_links_per_doc: int,
    legal_rps: float,
    wiki_rps: float,
    default_rps: float,
) -> Dict[str, object]:
    pack = json.loads(pack_path.read_text(encoding="utf-8"))
    pack_id = str(pack.get("pack_id") or pack_path.stem)
    user_agent = f"ITIR-suite/source-pack-manifest-pull ({pack_id})"
    generated_at = _utc_now_iso()
    pacer = _RequestPacer(legal_rps=legal_rps, wiki_rps=wiki_rps, default_rps=default_rps)

    out_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    docs: List[Dict[str, object]] = []
    errors: List[Dict[str, object]] = []

    for idx, (source, seed_url) in enumerate(_iter_seed_rows(pack), start=1):
        source_id = str(source.get("id") or f"source_{idx:03d}")
        source_name = str(source.get("name") or source_id)
        fetched_at = _utc_now_iso()
        doc_id = f"doc:{idx:04d}"
        row: Dict[str, object] = {
            "doc_id": doc_id,
            "source_id": source_id,
            "source_name": source_name,
            "url": seed_url,
            "fetched_at": fetched_at,
            "status": "error",
            "title": None,
            "content_type": None,
            "status_code": None,
            "final_url": None,
            "bytes": 0,
            "sha256": None,
            "outbound_links": [],
            "authority_links": [],
            "raw_path": None,
        }
        try:
            fetched = _fetch(seed_url, timeout=timeout, user_agent=user_agent, pacer=pacer)
            content = fetched["bytes"] if isinstance(fetched["bytes"], bytes) else b""
            final_url = str(fetched["final_url"])
            content_type = str(fetched["content_type"] or "")
            status_code = int(fetched["status_code"])
            digest = _sha256_bytes(content)
            suffix = ".html" if "html" in content_type.lower() else ".pdf" if "pdf" in content_type.lower() else ".bin"
            raw_name = f"{idx:04d}_{_slug(source_id)}_{_slug(final_url)}{suffix}"
            raw_path = raw_dir / raw_name
            raw_path.write_bytes(content)

            title = ""
            outbound_links: List[Dict[str, str]] = []
            if "html" in content_type.lower() or suffix == ".html":
                title, outbound_links = _parse_html_links(content, final_url, max_links=max_links_per_doc)

            authority_links: List[Dict[str, str]] = []
            seen_auth = set()
            for link in outbound_links:
                u = str(link.get("url") or "")
                t = str(link.get("text") or "")
                if not _is_authority_host(u):
                    continue
                key = (u, t)
                if key in seen_auth:
                    continue
                seen_auth.add(key)
                authority_links.append({"url": u, "text": t})
                if len(authority_links) >= max_authority_links_per_doc:
                    break

            row.update(
                {
                    "status": "ok",
                    "title": title or None,
                    "content_type": content_type,
                    "status_code": status_code,
                    "final_url": final_url,
                    "bytes": len(content),
                    "sha256": digest,
                    "outbound_links": outbound_links,
                    "authority_links": authority_links,
                    "raw_path": str(raw_path),
                }
            )
        except Exception as exc:  # pragma: no cover - runtime/network variance
            row["status"] = "error"
            row["error"] = f"{type(exc).__name__}: {exc}"
            errors.append({"doc_id": doc_id, "url": seed_url, "error": row["error"]})
        docs.append(row)

    docs_sorted = sorted(docs, key=lambda r: (str(r.get("fetched_at") or ""), str(r.get("doc_id") or "")))

    events: List[Dict[str, object]] = []
    for i, d in enumerate(docs_sorted, start=1):
        title = str(d.get("title") or "")
        final_url = str(d.get("final_url") or d.get("url") or "")
        text = title if title else final_url
        authority_labels = []
        for link in d.get("authority_links") or []:
            if isinstance(link, dict):
                label = _collapse_ws(str(link.get("text") or "")) or str(link.get("url") or "")
                authority_labels.append(label)
        event_id = f"ev:{i:04d}"
        events.append(
            {
                "event_id": event_id,
                "anchor": _iso_to_anchor(str(d.get("fetched_at") or generated_at)),
                "section": str(d.get("source_name") or ""),
                "text": text,
                "links": authority_labels[:24],
                "source_id": str(d.get("source_id") or ""),
                "url": final_url,
                "title": title or None,
                "status": d.get("status"),
                "doc_id": d.get("doc_id"),
            }
        )

    manifest = {
        "pack_id": pack_id,
        "generated_at": generated_at,
        "pack_path": str(pack_path),
        "contracts": pack.get("contracts") if isinstance(pack.get("contracts"), dict) else {},
        "fetch_policy": {
            "legal_rps": float(legal_rps),
            "wiki_rps": float(wiki_rps),
            "default_rps": float(default_rps),
        },
        "documents": docs_sorted,
        "errors": errors,
        "summary": {
            "documents_total": len(docs_sorted),
            "documents_ok": sum(1 for d in docs_sorted if d.get("status") == "ok"),
            "documents_error": sum(1 for d in docs_sorted if d.get("status") != "ok"),
            "authority_links_total": sum(len(d.get("authority_links") or []) for d in docs_sorted),
        },
    }

    timeline_payload = {
        "pack_id": pack_id,
        "generated_at": generated_at,
        "events": events,
    }
    timeline_graph = _timeline_graph(events, pack_id=pack_id)
    wiki_timeline = _wiki_timeline_payload(events, pack_id=pack_id)

    manifest_path = out_dir / "manifest.json"
    timeline_path = out_dir / "timeline.json"
    graph_path = out_dir / "timeline_graph.json"
    wiki_timeline_path = out_dir / f"wiki_timeline_{pack_id}.json"

    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    timeline_path.write_text(json.dumps(timeline_payload, indent=2, sort_keys=True), encoding="utf-8")
    graph_path.write_text(json.dumps(timeline_graph, indent=2, sort_keys=True), encoding="utf-8")
    wiki_timeline_path.write_text(json.dumps(wiki_timeline, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "ok": True,
        "pack_id": pack_id,
        "out_dir": str(out_dir),
        "manifest": str(manifest_path),
        "timeline": str(timeline_path),
        "timeline_graph": str(graph_path),
        "wiki_timeline": str(wiki_timeline_path),
        "summary": manifest["summary"],
    }


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Bounded source-pack pull -> manifest + chronology artifacts.")
    ap.add_argument(
        "--pack",
        dest="pack_path",
        type=Path,
        default=Path("SensibLaw/data/source_packs/legal_principles_au_v1.json"),
        help="Source-pack JSON path (default: %(default)s)",
    )
    ap.add_argument(
        "--out-dir",
        dest="out_dir",
        type=Path,
        default=Path("SensibLaw/demo/ingest/legal_principles_au_v1"),
        help="Output directory (default: %(default)s)",
    )
    ap.add_argument("--timeout", type=int, default=20, help="Per-request timeout seconds (default: %(default)s)")
    ap.add_argument(
        "--max-links-per-doc",
        type=int,
        default=160,
        help="Maximum outbound links retained per fetched HTML document (default: %(default)s)",
    )
    ap.add_argument(
        "--max-authority-links-per-doc",
        type=int,
        default=40,
        help="Maximum authority-host links retained per document (default: %(default)s)",
    )
    ap.add_argument(
        "--legal-rps",
        type=float,
        default=0.25,
        help="Max requests per second for legal hosts (default: %(default)s)",
    )
    ap.add_argument(
        "--wiki-rps",
        type=float,
        default=1.0,
        help="Max requests per second for wiki hosts (default: %(default)s)",
    )
    ap.add_argument(
        "--default-rps",
        type=float,
        default=0.5,
        help="Max requests per second for non-legal/non-wiki hosts (default: %(default)s)",
    )
    args = ap.parse_args(argv)

    result = run(
        pack_path=args.pack_path,
        out_dir=args.out_dir,
        timeout=max(1, int(args.timeout)),
        max_links_per_doc=max(1, int(args.max_links_per_doc)),
        max_authority_links_per_doc=max(1, int(args.max_authority_links_per_doc)),
        legal_rps=max(0.01, float(args.legal_rps)),
        wiki_rps=max(0.01, float(args.wiki_rps)),
        default_rps=max(0.01, float(args.default_rps)),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
