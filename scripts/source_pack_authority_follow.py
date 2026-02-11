#!/usr/bin/env python3
"""Bounded authority-link follower for source-pack manifests.

Reads authority links from a first-pass source-pack manifest and performs a
bounded follow pass:
- explicit breadth/depth caps (`--max-depth`, `--max-new-docs`)
- no unbounded crawl
- deterministic output manifests and chronology artifacts
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import urllib.parse
import urllib.request
from collections import deque
from html.parser import HTMLParser
from pathlib import Path
from typing import Deque, Dict, List, Optional, Set, Tuple


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


def _utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def _collapse_ws(text: str) -> str:
    return " ".join((text or "").split()).strip()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _slug(text: str) -> str:
    out = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in (text or "").strip())
    while "__" in out:
        out = out.replace("__", "_")
    return out.strip("._") or "artifact"


def _host(url: str) -> str:
    return (urllib.parse.urlparse(url).netloc or "").lower()


def _is_authority_host(url: str) -> bool:
    h = _host(url)
    return any(h.endswith(s) for s in AUTHORITY_HOST_SUFFIXES)


class _LinkAndTitleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_title = False
        self._title_buf: List[str] = []
        self._href: Optional[str] = None
        self._text_buf: List[str] = []
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
            self._href = href
            self._text_buf = []

    def handle_endtag(self, tag: str) -> None:
        t = (tag or "").lower()
        if t == "title":
            self.in_title = False
            return
        if t == "a":
            if self._href:
                self.links.append((self._href, _collapse_ws("".join(self._text_buf))))
            self._href = None
            self._text_buf = []

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self._title_buf.append(data)
            return
        if self._href is not None:
            self._text_buf.append(data)

    @property
    def title(self) -> str:
        return _collapse_ws("".join(self._title_buf))


def _fetch(url: str, timeout: int, user_agent: str) -> Dict[str, object]:
    req = urllib.request.Request(url, headers={"User-Agent": user_agent}, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310 - bounded fetch
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


def _parse_html_links(content: bytes, base_url: str, max_links: int) -> Tuple[str, List[Dict[str, str]], List[Dict[str, str]]]:
    text = content.decode("utf-8", errors="replace")
    parser = _LinkAndTitleParser()
    parser.feed(text)
    outbound: List[Dict[str, str]] = []
    authority: List[Dict[str, str]] = []
    seen_out = set()
    seen_auth = set()
    for href, txt in parser.links:
        u = urllib.parse.urljoin(base_url, href)
        if not u.startswith(("http://", "https://")):
            continue
        kout = (u, txt)
        if kout not in seen_out:
            seen_out.add(kout)
            outbound.append({"url": u, "text": txt})
            if len(outbound) >= max_links:
                break
        if _is_authority_host(u):
            ka = (u, txt)
            if ka not in seen_auth:
                seen_auth.add(ka)
                authority.append({"url": u, "text": txt})
    return parser.title, outbound, authority


def _iso_to_anchor(ts: str) -> Dict[str, object]:
    d = dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return {
        "year": d.year,
        "month": d.month,
        "day": d.day,
        "precision": "day",
        "text": d.strftime("%Y-%m-%d"),
        "kind": "ingest_follow",
    }


def _timeline_graph(events: List[Dict[str, object]], pack_id: str) -> Dict[str, object]:
    nodes: List[Dict[str, object]] = [{"id": f"pack:{pack_id}", "type": "pack", "label": pack_id}]
    edges: List[Dict[str, object]] = []
    time_seen: Set[str] = set()
    depth_seen: Set[int] = set()
    for ev in events:
        eid = str(ev.get("event_id") or "")
        day = str(((ev.get("anchor") or {}) if isinstance(ev.get("anchor"), dict) else {}).get("text") or "")
        depth = int(ev.get("depth") or 0)
        if day and day not in time_seen:
            time_seen.add(day)
            nodes.append({"id": f"time:{day}", "type": "time_day", "label": day})
        if depth not in depth_seen:
            depth_seen.add(depth)
            nodes.append({"id": f"depth:{depth}", "type": "depth", "label": f"depth {depth}"})
        nodes.append({"id": f"ev:{eid}", "type": "event", "label": str(ev.get("text") or "")})
        if day:
            edges.append({"from": f"time:{day}", "to": f"ev:{eid}", "type": "TIME_BIN"})
        edges.append({"from": f"depth:{depth}", "to": f"ev:{eid}", "type": "DEPTH_BIN"})
        edges.append({"from": f"pack:{pack_id}", "to": f"ev:{eid}", "type": "HAS_EVENT"})
    for i in range(len(events) - 1):
        a = str(events[i].get("event_id") or "")
        b = str(events[i + 1].get("event_id") or "")
        if a and b:
            edges.append({"from": f"ev:{a}", "to": f"ev:{b}", "type": "NEXT_CHRONO", "order": i + 1})
    return {
        "graph_id": f"source_pack_follow_timeline_{pack_id}",
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
                "url": ev.get("url"),
                "title": ev.get("title"),
                "depth": ev.get("depth"),
                "parent_url": ev.get("parent_url"),
            }
        )
    return {
        "snapshot": {
            "title": f"Source Pack Follow {pack_id}",
            "wiki": "source_pack_follow",
            "revid": None,
            "source_url": None,
        },
        "events": out_events,
    }


def _load_manifest(path: Path) -> Dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def run(manifest_path: Path, out_dir: Path, timeout: int, max_depth: int, max_new_docs: int, max_links_per_doc: int, max_authority_links_per_doc: int) -> Dict[str, object]:
    manifest = _load_manifest(manifest_path)
    pack_id = str(manifest.get("pack_id") or "source_pack")
    user_agent = f"ITIR-suite/source-pack-authority-follow ({pack_id})"
    generated_at = _utc_now_iso()
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    docs = manifest.get("documents") or []
    if not isinstance(docs, list):
        docs = []

    queue: Deque[Tuple[int, str, str, str]] = deque()
    seed_seen: Set[str] = set()
    for d in docs:
        if not isinstance(d, dict):
            continue
        parent_doc_id = str(d.get("doc_id") or "")
        links = d.get("authority_links") or []
        if not isinstance(links, list):
            continue
        for link in links:
            if not isinstance(link, dict):
                continue
            u = str(link.get("url") or "").strip()
            t = _collapse_ws(str(link.get("text") or ""))
            if not u or u in seed_seen:
                continue
            seed_seen.add(u)
            queue.append((1, u, parent_doc_id, t))

    followed_docs: List[Dict[str, object]] = []
    errors: List[Dict[str, object]] = []
    visited: Set[str] = set()

    while queue and len(followed_docs) < max_new_docs:
        depth, url, parent_doc_id, parent_anchor = queue.popleft()
        if depth > max_depth:
            continue
        if url in visited:
            continue
        visited.add(url)

        doc_id = f"fdoc:{len(followed_docs)+1:04d}"
        fetched_at = _utc_now_iso()
        row: Dict[str, object] = {
            "doc_id": doc_id,
            "depth": depth,
            "url": url,
            "parent_doc_id": parent_doc_id,
            "parent_anchor_text": parent_anchor,
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
            fetched = _fetch(url, timeout=timeout, user_agent=user_agent)
            content = fetched["bytes"] if isinstance(fetched["bytes"], bytes) else b""
            final_url = str(fetched["final_url"])
            content_type = str(fetched["content_type"] or "")
            status_code = int(fetched["status_code"])
            digest = _sha256_bytes(content)
            suffix = ".html" if "html" in content_type.lower() else ".pdf" if "pdf" in content_type.lower() else ".bin"
            raw_name = f"{len(followed_docs)+1:04d}_{_slug(final_url)}{suffix}"
            raw_path = raw_dir / raw_name
            raw_path.write_bytes(content)

            title = ""
            outbound_links: List[Dict[str, str]] = []
            authority_links: List[Dict[str, str]] = []
            if "html" in content_type.lower() or suffix == ".html":
                title, outbound_links, authority_links = _parse_html_links(content, final_url, max_links=max_links_per_doc)
            if len(authority_links) > max_authority_links_per_doc:
                authority_links = authority_links[:max_authority_links_per_doc]

            row.update(
                {
                    "status": "ok",
                    "title": title or None,
                    "content_type": content_type,
                    "status_code": status_code,
                    "final_url": final_url,
                    "bytes": len(content),
                    "sha256": digest,
                    "outbound_links": outbound_links[:max_links_per_doc],
                    "authority_links": authority_links,
                    "raw_path": str(raw_path),
                }
            )

            if depth < max_depth:
                for al in authority_links:
                    nu = str(al.get("url") or "").strip()
                    nt = _collapse_ws(str(al.get("text") or ""))
                    if not nu or nu in visited:
                        continue
                    queue.append((depth + 1, nu, doc_id, nt))
        except Exception as exc:  # pragma: no cover
            row["status"] = "error"
            row["error"] = f"{type(exc).__name__}: {exc}"
            errors.append({"doc_id": doc_id, "url": url, "error": row["error"]})

        followed_docs.append(row)

    followed_docs = sorted(followed_docs, key=lambda r: (str(r.get("fetched_at") or ""), str(r.get("doc_id") or "")))

    events: List[Dict[str, object]] = []
    for i, d in enumerate(followed_docs, start=1):
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
                "section": "Authority follow",
                "text": text,
                "links": authority_labels[:24],
                "depth": int(d.get("depth") or 0),
                "url": final_url,
                "title": title or None,
                "status": d.get("status"),
                "doc_id": d.get("doc_id"),
                "parent_url": d.get("url"),
            }
        )

    payload = {
        "pack_id": pack_id,
        "generated_at": generated_at,
        "source_manifest": str(manifest_path),
        "follow_contract": {
            "max_depth": max_depth,
            "max_new_docs": max_new_docs,
            "max_links_per_doc": max_links_per_doc,
            "max_authority_links_per_doc": max_authority_links_per_doc,
        },
        "documents": followed_docs,
        "errors": errors,
        "summary": {
            "documents_total": len(followed_docs),
            "documents_ok": sum(1 for d in followed_docs if d.get("status") == "ok"),
            "documents_error": sum(1 for d in followed_docs if d.get("status") != "ok"),
            "max_depth_observed": max((int(d.get("depth") or 0) for d in followed_docs), default=0),
        },
    }
    timeline_payload = {"pack_id": pack_id, "generated_at": generated_at, "events": events}
    graph_payload = _timeline_graph(events, pack_id=f"{pack_id}_follow")
    wiki_timeline = _wiki_timeline_payload(events, pack_id=f"{pack_id}_follow")

    manifest_out = out_dir / "follow_manifest.json"
    timeline_out = out_dir / "follow_timeline.json"
    graph_out = out_dir / "follow_timeline_graph.json"
    wiki_timeline_out = out_dir / f"wiki_timeline_{pack_id}_follow.json"

    manifest_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    timeline_out.write_text(json.dumps(timeline_payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    graph_out.write_text(json.dumps(graph_payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    wiki_timeline_out.write_text(json.dumps(wiki_timeline, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "ok": True,
        "pack_id": pack_id,
        "out_dir": str(out_dir),
        "follow_manifest": str(manifest_out),
        "follow_timeline": str(timeline_out),
        "follow_timeline_graph": str(graph_out),
        "wiki_timeline": str(wiki_timeline_out),
        "summary": payload["summary"],
    }


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Bounded authority-link follow pass from source-pack manifest.")
    ap.add_argument(
        "--manifest",
        type=Path,
        default=Path("SensibLaw/demo/ingest/legal_principles_au_v1/manifest.json"),
        help="Input first-pass manifest path (default: %(default)s)",
    )
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=Path("SensibLaw/demo/ingest/legal_principles_au_v1/follow"),
        help="Output directory (default: %(default)s)",
    )
    ap.add_argument("--timeout", type=int, default=20, help="Per-request timeout seconds (default: %(default)s)")
    ap.add_argument("--max-depth", type=int, default=2, help="Max follow depth (default: %(default)s)")
    ap.add_argument("--max-new-docs", type=int, default=40, help="Max followed documents (default: %(default)s)")
    ap.add_argument("--max-links-per-doc", type=int, default=140, help="Max outbound links retained per doc (default: %(default)s)")
    ap.add_argument(
        "--max-authority-links-per-doc",
        type=int,
        default=30,
        help="Max authority links retained/enqueued per doc (default: %(default)s)",
    )
    args = ap.parse_args(argv)

    result = run(
        manifest_path=args.manifest,
        out_dir=args.out_dir,
        timeout=max(1, int(args.timeout)),
        max_depth=max(1, int(args.max_depth)),
        max_new_docs=max(1, int(args.max_new_docs)),
        max_links_per_doc=max(1, int(args.max_links_per_doc)),
        max_authority_links_per_doc=max(1, int(args.max_authority_links_per_doc)),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
