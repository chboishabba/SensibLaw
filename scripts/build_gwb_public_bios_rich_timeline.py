#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable


RAW_ROOT = Path("SensibLaw/demo/ingest/gwb/public_bios_v1/raw")
DEFAULT_OUT = Path("SensibLaw/demo/ingest/gwb/public_bios_v1/wiki_timeline_gwb_public_bios_v1_rich.json")

_KEYWORD_CUES = (
    "signed",
    "veto",
    "vetoed",
    "nominated",
    "confirmed",
    "confirmation",
    "supreme court",
    "court",
    "congress",
    "act",
    "law",
    "authorization",
    "iraq",
    "afghanistan",
    "senate",
    "justice",
    "military commissions",
    "schip",
    "stem cell",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _anchor_from_iso(ts: str) -> dict[str, object]:
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return {
        "year": dt.year,
        "month": dt.month,
        "day": dt.day,
        "precision": "day",
        "text": f"{dt.year:04d}-{dt.month:02d}-{dt.day:02d}",
        "kind": "ingest",
    }


def _collapse_ws(text: str) -> str:
    return " ".join((text or "").split()).strip()


def _split_sentences(text: str) -> list[str]:
    text = _collapse_ws(text)
    if not text:
        return []
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]


def _contains_signal(text: str) -> bool:
    low = text.lower()
    return any(cue in low for cue in _KEYWORD_CUES)


class _BioHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_title = False
        self.skip_depth = 0
        self.block_stack: list[str] = []
        self.current_parts: list[str] = []
        self.title_parts: list[str] = []
        self.meta_descriptions: list[str] = []
        self.blocks: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:  # pragma: no cover - stdlib callback
        attr_map = {k.lower(): (v or "") for k, v in attrs}
        low_tag = tag.lower()
        if low_tag in {"script", "style", "noscript"}:
            self.skip_depth += 1
            return
        if low_tag == "title":
            self.in_title = True
        if low_tag == "meta":
            name = attr_map.get("name", "").lower()
            prop = attr_map.get("property", "").lower()
            content = _collapse_ws(unescape(attr_map.get("content", "")))
            if content and (name == "description" or prop in {"og:description", "twitter:description"}):
                if content not in self.meta_descriptions:
                    self.meta_descriptions.append(content)
        if self.skip_depth == 0 and low_tag in {"p", "figcaption", "h1", "h2", "h3"}:
            self.block_stack.append(low_tag)
            self.current_parts = []

    def handle_endtag(self, tag: str) -> None:  # pragma: no cover - stdlib callback
        low_tag = tag.lower()
        if low_tag in {"script", "style", "noscript"} and self.skip_depth > 0:
            self.skip_depth -= 1
            return
        if low_tag == "title":
            self.in_title = False
        if self.skip_depth == 0 and self.block_stack and low_tag == self.block_stack[-1]:
            text = _collapse_ws(unescape(" ".join(self.current_parts)))
            if text:
                self.blocks.append({"tag": low_tag, "text": text})
            self.block_stack.pop()
            self.current_parts = []

    def handle_data(self, data: str) -> None:  # pragma: no cover - stdlib callback
        if self.skip_depth > 0:
            return
        if self.in_title:
            self.title_parts.append(data)
        if self.block_stack:
            self.current_parts.append(data)


@dataclass(frozen=True)
class _Doc:
    path: Path

    @property
    def title(self) -> str:
        return self.path.name


def _iter_docs(root: Path) -> Iterable[_Doc]:
    for path in sorted(root.glob("*.html")):
        yield _Doc(path=path)


def _doc_url(path: Path) -> str | None:
    stem = path.name
    marker = "_https_"
    if marker not in stem:
        return None
    raw = stem.split(marker, 1)[1]
    if raw.endswith(".html.html"):
        raw = raw[: -len(".html.html")]
    elif raw.endswith(".html"):
        raw = raw[: -len(".html")]
    raw = raw.replace("_", "/")
    return f"https://{raw}"


def _doc_snippets(path: Path, *, max_snippets: int, snippet_chars: int) -> tuple[str, list[str]]:
    parser = _BioHTMLParser()
    parser.feed(path.read_text(encoding="utf-8", errors="ignore"))
    title = _collapse_ws(unescape(" ".join(parser.title_parts))) or path.name

    candidate_blocks: list[str] = []
    for desc in parser.meta_descriptions:
        if desc and desc not in candidate_blocks:
            candidate_blocks.append(desc)
    for block in parser.blocks:
        text = block["text"]
        if len(text) < 40:
            continue
        if not _contains_signal(text):
            continue
        if text not in candidate_blocks:
            candidate_blocks.append(text)

    sentences: list[str] = []
    for block in candidate_blocks:
        for sent in _split_sentences(block):
            if len(sent) < 30:
                continue
            if sent not in sentences:
                sentences.append(sent)

    snippets: list[str] = []
    buf = ""
    for sent in sentences:
        if not buf:
            buf = sent
            continue
        if len(buf) + 1 + len(sent) <= snippet_chars:
            buf = f"{buf} {sent}"
            continue
        snippets.append(buf)
        buf = sent
        if len(snippets) >= max_snippets:
            buf = ""
            break
    if buf and len(snippets) < max_snippets:
        snippets.append(buf)
    if not snippets:
        fallback = next((desc for desc in parser.meta_descriptions if desc), title)
        snippets = [fallback[:snippet_chars]]
    return title, snippets


def build_public_bios_timeline(*, raw_root: Path, out_path: Path, max_docs: int, max_snippets_per_doc: int, snippet_chars: int) -> dict[str, object]:
    generated_at = _utc_now_iso()
    anchor = _anchor_from_iso(generated_at)
    events: list[dict[str, object]] = []
    docs = list(_iter_docs(raw_root))[: max(0, max_docs)]
    ev_i = 0
    for doc in docs:
        title, snippets = _doc_snippets(doc.path, max_snippets=max_snippets_per_doc, snippet_chars=snippet_chars)
        doc_url = _doc_url(doc.path)
        for snippet in snippets:
            ev_i += 1
            row: dict[str, object] = {
                "event_id": f"ev:{ev_i:04d}",
                "anchor": anchor,
                "section": f"Public bio doc: {title}",
                "text": snippet,
                "links": [],
                "source_id": "gwb_public_bios_web",
                "title": title,
                "path": str(doc.path.resolve()),
                "root_actor": "George W. Bush",
                "root_surname": "Bush",
            }
            if doc_url:
                row["url"] = doc_url
            events.append(row)

    payload = {
        "snapshot": {"title": "GWB public bios v1 rich", "wiki": "gwb_public_bios_v1_rich", "revid": None, "source_url": None},
        "events": events,
        "generated_at": generated_at,
        "raw_root": str(raw_root.resolve()),
        "notes": "Auto-built from local raw public-bios HTML. Events are cue-filtered snippet windows for broader GWB extraction.",
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
    return {"ok": True, "out": str(out_path), "docs": len(docs), "events": len(events)}


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a richer GWB public-bios timeline from raw HTML pages.")
    ap.add_argument("--raw-root", type=Path, default=RAW_ROOT, help="Directory containing raw public-bios HTML files.")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Output timeline JSON path.")
    ap.add_argument("--max-docs", type=int, default=20, help="Max docs processed.")
    ap.add_argument("--max-snippets-per-doc", type=int, default=12, help="Max snippets emitted per doc.")
    ap.add_argument("--snippet-chars", type=int, default=420, help="Max characters per snippet.")
    args = ap.parse_args()

    result = build_public_bios_timeline(
        raw_root=args.raw_root.resolve(),
        out_path=args.out,
        max_docs=int(args.max_docs),
        max_snippets_per_doc=int(args.max_snippets_per_doc),
        snippet_chars=int(args.snippet_chars),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
