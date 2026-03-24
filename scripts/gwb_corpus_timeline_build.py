#!/usr/bin/env python3
from __future__ import annotations

"""
Build a local "wiki_timeline_*.json" style timeline from the GWB demo corpus folder.

Why this exists:
- The AAO UI is DB-first (wiki_timeline_aoo.sqlite), but we still need a deterministic
  timeline input artifact whose path is stored in the DB run metadata.
- We want the AAO extractor to emit per-row citations pointing back to local PDF/EPUB
  artifacts so they show up in the Sources lane.

This script intentionally keeps extraction light:
- PDF: best-effort text extraction via pdfminer.six (if installed), fallback to filename-only.
- EPUB: best-effort unzip + strip HTML, fallback to filename-only.
- Event text is chunked into short snippets so the AAO extractor stays responsive.
"""

import argparse
import json
import posixpath
import re
import shutil
import subprocess
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET
from typing import Iterable, List, Optional


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _anchor_from_iso(ts: str) -> dict:
    # Matches the anchor schema used by existing source-pack timelines.
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        dt = datetime.now(timezone.utc)
    return {
        "year": dt.year,
        "month": dt.month,
        "day": dt.day,
        "precision": "day",
        "text": f"{dt.year:04d}-{dt.month:02d}-{dt.day:02d}",
        "kind": "ingest",
    }


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: List[str] = []

    def handle_data(self, data: str) -> None:  # pragma: no cover - stdlib callback
        if data:
            self.parts.append(data)

    def text(self) -> str:
        return " ".join(self.parts)


def _collapse_ws(s: str) -> str:
    # Collapse whitespace without regex (keeps the ingestion layer deterministic and lightweight).
    return " ".join((s or "").split()).strip()

_BOILERPLATE_MARKERS = [
    "all rights reserved",
    "no part of this book",
    "library of congress",
    "cataloging-in-publication",
    "printed in the united states",
    "copyright",
    "isbn",
]

_CORPUS_PRIORITY_CUES = (
    "no child left behind",
    "john roberts",
    "samuel alito",
    "harriet miers",
    "military commissions act",
    "foreign intelligence surveillance act",
    "fisa",
    "surveillance",
    "stem cell",
    "schip",
    "syria accountability",
    "iraq",
    "authorization",
    "supreme court",
    "court",
    "congress",
    "senate",
    "signed",
    "veto",
    "nominated",
)


def _is_tocish(s: str) -> bool:
    s2 = s.strip()
    if not s2:
        return True
    low = s2.lower()

    def _is_word_char(ch: str) -> bool:
        # Approximate word-boundaries for ASCII-ish ingestion (similar spirit to regex \b).
        return ch.isalnum() or ch == "_"

    def _count_digit_tokens(max_len: int | None = None) -> int:
        # Count contiguous digit runs delimited by non-word chars, without regex.
        n = 0
        i = 0
        while i < len(s2):
            if not s2[i].isdigit():
                i += 1
                continue
            prev = s2[i - 1] if i > 0 else ""
            if prev and _is_word_char(prev):
                i += 1
                continue
            j = i
            while j < len(s2) and s2[j].isdigit():
                j += 1
            nxt = s2[j] if j < len(s2) else ""
            if nxt and _is_word_char(nxt):
                i = j + 1
                continue
            if max_len is None or (j - i) <= max_len:
                n += 1
            i = j + 1
        return n

    if "contents" in low and _count_digit_tokens() >= 4:
        return True
    # TOCs often look like: "INTRODUCTION 1 Foo 2 Bar 3 Baz ..."
    nums = _count_digit_tokens(max_len=3)
    if nums >= 8 and len(s2) < 700:
        return True
    if "chapter" in low and nums >= 3 and s2.count(",") >= 4:
        return True
    if re.search(r"chapter\s+\d", low) and s2.count(",") >= 6:
        return True
    if any(m in low for m in _BOILERPLATE_MARKERS):
        return True
    return False


def _epub_container_opf_path(zf: zipfile.ZipFile) -> str:
    # META-INF/container.xml points to the package (OPF).
    raw = zf.read("META-INF/container.xml")
    root = ET.fromstring(raw)
    # Ignore namespaces by matching suffixes.
    for elem in root.iter():
        if elem.tag.endswith("rootfile") and "full-path" in elem.attrib:
            return elem.attrib["full-path"]
    raise ValueError("no rootfile full-path in container.xml")


def _epub_spine_items(zf: zipfile.ZipFile, opf_path: str) -> List[str]:
    raw = zf.read(opf_path)
    root = ET.fromstring(raw)

    manifest: dict[str, dict[str, str]] = {}
    spine: List[str] = []

    for elem in root.iter():
        if elem.tag.endswith("item") and "id" in elem.attrib and "href" in elem.attrib:
            manifest[elem.attrib["id"]] = {
                "href": elem.attrib["href"],
                "media-type": elem.attrib.get("media-type", ""),
                "properties": elem.attrib.get("properties", ""),
            }
        elif elem.tag.endswith("itemref") and "idref" in elem.attrib:
            spine.append(elem.attrib["idref"])

    base_dir = posixpath.dirname(opf_path)
    out: List[str] = []
    for idref in spine:
        item = manifest.get(idref)
        if not item:
            continue
        href = item.get("href", "")
        if not href:
            continue
        props = item.get("properties", "")
        if "nav" in props.split():
            continue

        full = posixpath.normpath(posixpath.join(base_dir, href)) if base_dir else posixpath.normpath(href)
        low = full.lower()
        if not low.endswith((".xhtml", ".html", ".htm")):
            continue
        # Common frontmatter filenames.
        if any(k in low for k in ("toc", "contents", "title", "cover", "copyright", "dedication", "colophon")):
            continue

        out.append(full)
    return out


def _split_sentences(s: str) -> List[str]:
    s = _collapse_ws(s)
    if not s:
        return []
    # Deliberately simple: deterministic and dependency-free.
    parts = re.split(r"(?<=[.!?])\s+", s)
    out = []
    for p in parts:
        p2 = p.strip()
        if not p2:
            continue
        if _is_tocish(p2):
            continue
        out.append(p2)
    return out


def _sentence_signal_score(s: str) -> int:
    low = s.lower()
    score = 0
    for cue in _CORPUS_PRIORITY_CUES:
        if cue in low:
            score += 1
    if "signed" in low and ("act" in low or "law" in low or "proclamation" in low):
        score += 2
    if "nominated" in low and ("john roberts" in low or "samuel alito" in low or "harriet miers" in low):
        score += 2
    if "surveillance" in low and ("fisa" in low or "foreign intelligence surveillance act" in low):
        score += 2
    return score


def _chunk_snippets(sentences: List[str], *, max_snippets: int, snippet_chars: int) -> List[str]:
    if not sentences:
        return []

    scored = [(idx, _sentence_signal_score(sent)) for idx, sent in enumerate(sentences)]
    priority_indices = [idx for idx, score in sorted(scored, key=lambda item: (-item[1], item[0])) if score > 0]
    priority_set = set(priority_indices)
    ordered = [sentences[idx] for idx in priority_indices] + [sent for idx, sent in enumerate(sentences) if idx not in priority_set]

    snippets: List[str] = []
    buf = ""
    for sent in ordered:
        if not sent:
            continue
        if _sentence_signal_score(sent) >= 4:
            if buf and len(snippets) < max_snippets:
                snippets.append(buf)
                buf = ""
            if sent not in snippets:
                snippets.append(sent[:snippet_chars])
            if len(snippets) >= max_snippets:
                break
            continue
        if not buf:
            buf = sent
            continue
        if len(buf) + 1 + len(sent) <= snippet_chars:
            buf = f"{buf} {sent}"
        else:
            snippets.append(buf)
            buf = sent
        if len(snippets) >= max_snippets:
            buf = ""
            break
    if buf and len(snippets) < max_snippets:
        snippets.append(buf)
    return snippets


def _pdf_text(path: Path, *, limit_chars: int) -> str:
    def _via_pdftotext() -> str:
        exe = shutil.which("pdftotext")
        if not exe:
            return ""
        # Keep it bounded: enough text to emit many snippet-events without spending ages.
        # `-` writes to stdout.
        proc = subprocess.run(
            [exe, "-f", "1", "-l", "60", "-layout", "-nopgbrk", str(path), "-"],
            check=False,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            return ""
        txt2 = _collapse_ws(proc.stdout or "")
        return txt2[:limit_chars] if txt2 else ""

    try:
        from pdfminer.high_level import extract_text  # type: ignore
    except Exception:
        return _via_pdftotext()
    try:
        txt = extract_text(str(path))
    except Exception:
        return _via_pdftotext()
    txt = _collapse_ws(txt)
    if not txt:
        return _via_pdftotext()
    return txt[:limit_chars]


def _epub_text(path: Path, *, limit_chars: int) -> str:
    try:
        with zipfile.ZipFile(path, "r") as zf:
            # Prefer the OPF spine order; fallback to a heuristic list.
            try:
                opf_path = _epub_container_opf_path(zf)
                names = _epub_spine_items(zf, opf_path)
                # Many books still have 1-2 non-content spine items up front.
                names = names[2:]
            except Exception:
                names = [n for n in zf.namelist() if n.lower().endswith((".xhtml", ".html", ".htm"))]
                names.sort()
            out_parts: List[str] = []
            total = 0
            for n in names:
                if total >= limit_chars:
                    break
                try:
                    raw = zf.read(n)
                except Exception:
                    continue
                # EPUB content is usually UTF-8; fall back to latin-1 to avoid hard failure.
                try:
                    html = raw.decode("utf-8", errors="ignore")
                except Exception:
                    html = raw.decode("latin-1", errors="ignore")
                parser = _TextExtractor()
                try:
                    parser.feed(html)
                except Exception:
                    continue
                txt = _collapse_ws(parser.text())
                if not txt:
                    continue
                if _is_tocish(txt[:800]):
                    continue
                take = txt[: max(0, limit_chars - total)]
                if take:
                    out_parts.append(take)
                    total += len(take)
            return _collapse_ws(" ".join(out_parts))[:limit_chars]
    except Exception:
        return ""


@dataclass(frozen=True)
class _Doc:
    path: Path
    title: str
    kind: str


def _iter_docs(root: Path) -> Iterable[_Doc]:
    for p in sorted(root.glob("*.pdf")):
        yield _Doc(path=p, title=p.name, kind="pdf")
    for p in sorted(root.glob("*.epub")):
        yield _Doc(path=p, title=p.name, kind="epub")


def _root_actor_for_doc_title(title: str) -> tuple[str, str]:
    """
    Optional per-doc narrator/author hint to improve AAO subject resolution.

    This is intentionally conservative: only enable where the text is clearly a first-person memoir.
    """
    low = (title or "").lower()
    if "decision points" in low and "bush, george w" in low:
        return ("George W. Bush", "Bush")
    return ("", "")


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a local corpus wiki_timeline JSON for AAO extraction.")
    ap.add_argument("--root", type=Path, default=Path("SensibLaw/demo/ingest/gwb"), help="Corpus root (default: %(default)s)")
    ap.add_argument(
        "--out",
        type=Path,
        default=Path("SensibLaw/demo/ingest/gwb/corpus_v1/wiki_timeline_gwb_corpus_v1.json"),
        help="Output timeline JSON path (default: %(default)s)",
    )
    ap.add_argument("--max-docs", type=int, default=20, help="Max docs processed (default: %(default)s)")
    ap.add_argument("--max-snippets-per-doc", type=int, default=80, help="Max snippet events per doc (default: %(default)s)")
    ap.add_argument("--snippet-chars", type=int, default=420, help="Max characters per snippet event (default: %(default)s)")
    ap.add_argument("--extract-chars-per-doc", type=int, default=1_200_000, help="Max extracted chars per doc (default: %(default)s)")
    args = ap.parse_args()

    root = args.root.resolve()
    out_path = args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)

    generated_at = _utc_now_iso()
    anchor = _anchor_from_iso(generated_at)

    docs = list(_iter_docs(root))[: max(0, int(args.max_docs))]
    events: List[dict] = []
    ev_i = 0
    per_doc_snips: List[tuple[_Doc, List[str]]] = []

    for d in docs:
        # Extract a bounded amount of raw text; if extraction fails, fall back to a filename-only stub row.
        txt = ""
        if d.kind == "pdf":
            txt = _pdf_text(d.path, limit_chars=int(args.extract_chars_per_doc))
        elif d.kind == "epub":
            txt = _epub_text(d.path, limit_chars=int(args.extract_chars_per_doc))

        sents = _split_sentences(txt)
        if not sents:
            sents = [d.title]

        # Chunk sentences into bounded snippet rows.
        snippets = _chunk_snippets(
            sents,
            max_snippets=int(args.max_snippets_per_doc),
            snippet_chars=int(args.snippet_chars),
        )
        per_doc_snips.append((d, snippets))

    # Interleave snippets across docs so limited `--max-events` extraction still touches every file.
    max_len = max((len(snips) for _, snips in per_doc_snips), default=0)
    for i in range(max_len):
        for d, snips in per_doc_snips:
            if i >= len(snips):
                continue
            snip = snips[i]
            root_actor, root_surname = _root_actor_for_doc_title(d.title)
            ev_i += 1
            row = {
                "event_id": f"ev:{ev_i:04d}",
                "anchor": anchor,
                "section": f"Corpus doc: {d.title}",
                "text": snip,
                "links": [],
                "source_id": "gwb_corpus_local",
                "title": d.title,
                # Use `path` (not `url`) so wiki_timeline_aoo_extract emits follow mode=path.
                "path": str(d.path),
            }
            if root_actor:
                row["root_actor"] = root_actor
            if root_surname:
                row["root_surname"] = root_surname
            events.append(row)

    payload = {
        "snapshot": {"title": "GWB corpus v1", "wiki": "gwb_corpus_v1", "revid": None, "source_url": None},
        "events": events,
        "generated_at": generated_at,
        "corpus_root": str(root),
        "notes": "Auto-built from local PDF/EPUB corpus. Events are snippet windows for AAO extraction; non-authoritative.",
    }

    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True), encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(out_path), "docs": len(docs), "events": len(events)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
