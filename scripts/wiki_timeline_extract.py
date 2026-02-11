#!/usr/bin/env python3
"""Extract date-anchored event timeline candidates from a Wikipedia snapshot JSON.

Input: snapshot JSON produced by `wiki_pull_api.py` (includes wikitext + provenance).
Output: a gitignored timeline candidate JSON artifact suitable for curation and visualization.

This is not a causal graph generator. It extracts:
- date anchors (year/month/day when explicit)
- a short event text span (sentence/paragraph line)
- section label (best-effort)
- linked titles present in the candidate (identity glue)
- provenance: source_url + revid + snapshot_path
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


HEADING_RE = re.compile(r"^(=+)\s*(.+?)\s*\1\s*$")

# Date anchors we care about. Keep this strict initially.
ON_MDY_RE = re.compile(
    r"^\s*On\s+([A-Z][a-z]+)\s+(\d{1,2}),\s+(\d{4})\b",
)
IN_MY_RE = re.compile(
    r"^\s*In\s+([A-Z][a-z]+)\s+(\d{4})\b",
)
IN_Y_RE = re.compile(
    r"^\s*In\s+(\d{4})\b",
)

REFNOTE_RE = re.compile(r"\[(?:\d+|note\s+\d+)\]")

# Protect common abbreviations so naive sentence splitting doesn't truncate
# timeline candidates (e.g. "U.S." should not end a sentence by default).
ABBREV_TOKENS = {
    "U.S.",
    "U.K.",
    "D.C.",
    "U.S.C.",
    "Mr.",
    "Mrs.",
    "Ms.",
    "Dr.",
    "St.",
    "Jr.",
    "Sr.",
    "Sen.",
    "Rep.",
    "Gov.",
    "Pres.",
}

SEP_TEMPLATES = [
    # Wikipedia commonly uses {{snd}} as a spaced ndash separator.
    re.compile(r"\{\{\s*snd\s*\}\}", flags=re.IGNORECASE),
]

# Citation/reference tails that occasionally survive strip_code and pollute event text.
# Example:
#   "... projects,Bush, George W."
#   "... exam.Rutenberg, Jim (May 17, 2004)."
CITATION_TAIL_RE = [
    re.compile(
        r"(?:,|\.)\s*[A-Z][a-z]+,\s*[A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,3}\s*\([^)]{3,60}\)\.?$"
    ),
    re.compile(
        r"(?:,|\.)\s*[A-Z][a-z]+,\s*[A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,3}\.?$"
    ),
    re.compile(
        r"(?:,|\.)\s*[A-Z][a-z]+,\s*[A-Z][^,]{1,180},\s*[A-Z][a-z]+\s+\d{1,2},\s+\d{4}\.?$"
    ),
]


def _utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def _load_snapshot(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _strip_refs(text: str) -> str:
    # Remove footnote markers like [485]
    return REFNOTE_RE.sub("", text)


def _collapse_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _wikitext_links(text: str) -> List[str]:
    # Extract `[[Title|...]]` and normalize to Title.
    out: List[str] = []
    for m in re.finditer(r"\[\[([^\]\|#]+)(?:[|#][^\]]*)?\]\]", text):
        title = m.group(1).strip()
        if not title:
            continue
        if title.startswith(("Category:", "File:", "Template:", "Wikipedia:", "Help:", "Portal:", "Special:")):
            continue
        if title not in out:
            out.append(title)
    return out


def _links_in_sentence(para_wikitext: str, sentence_plain: str) -> List[str]:
    """Best-effort sentence-local link capture.

    We extract wikilinks from the paragraph, then include only those whose
    surface form appears in the stripped sentence text. This reduces the "wide
    net" effect where a paragraph-level link list pulls in irrelevant entities.
    """

    sentence_norm = _collapse_ws(sentence_plain).lower()
    if not sentence_norm:
        return []

    # Use mwparserfromhell if available for better surface-form extraction.
    try:
        import mwparserfromhell  # type: ignore

        code = mwparserfromhell.parse(para_wikitext)
        out: List[str] = []
        for wl in code.filter_wikilinks(recursive=True):
            title = str(wl.title).strip()
            if not title:
                continue
            if title.startswith(("Category:", "File:", "Template:", "Wikipedia:", "Help:", "Portal:", "Special:")):
                continue
            # Surface form: piped text if present, else title.
            surface = str(wl.text).strip() if wl.text is not None else ""
            surface = surface or title
            surface_norm = _collapse_ws(surface).lower()
            if surface_norm and surface_norm in sentence_norm:
                if title not in out:
                    out.append(title)
        return out
    except Exception:
        # Fallback: use all paragraph links if we can't parse surface forms.
        return _wikitext_links(para_wikitext)


@dataclass(frozen=True)
class DateAnchor:
    year: int
    month: Optional[int] = None
    day: Optional[int] = None
    precision: str = "year"  # year|month|day
    text: str = ""
    kind: str = "explicit"  # explicit|weak

    def to_json(self) -> dict:
        return {
            "year": self.year,
            "month": self.month,
            "day": self.day,
            "precision": self.precision,
            "text": self.text,
            "kind": self.kind,
        }


def _parse_anchor(line: str) -> Optional[DateAnchor]:
    m = ON_MDY_RE.match(line)
    if m:
        month_name = m.group(1).lower()
        month = MONTHS.get(month_name)
        if not month:
            return None
        day = int(m.group(2))
        year = int(m.group(3))
        return DateAnchor(year=year, month=month, day=day, precision="day", text=m.group(0).strip(), kind="explicit")

    m = IN_MY_RE.match(line)
    if m:
        month_name = m.group(1).lower()
        month = MONTHS.get(month_name)
        if not month:
            return None
        year = int(m.group(2))
        return DateAnchor(year=year, month=month, day=None, precision="month", text=m.group(0).strip(), kind="explicit")

    m = IN_Y_RE.match(line)
    if m:
        year = int(m.group(1))
        # Year-only anchors are weaker; still useful as timeline scaffolding.
        return DateAnchor(year=year, month=None, day=None, precision="year", text=m.group(0).strip(), kind="weak")

    return None


def _iter_section_paragraphs(wikitext: str) -> Iterable[Tuple[str, str]]:
    """Yield (section, paragraph_wikitext) pairs."""
    section = "(lead)"
    buf: List[str] = []

    def flush():
        nonlocal buf
        para = "\n".join(buf).strip()
        buf = []
        if para:
            yield (section, para)

    for raw_line in wikitext.splitlines():
        line = raw_line.rstrip("\n")
        hm = HEADING_RE.match(line)
        if hm:
            # Heading boundary flushes current paragraph buffer.
            for item in flush():
                yield item
            title = hm.group(2).strip()
            section = title if title else section
            continue

        # Skip maintenance and category lines.
        if line.startswith(("[[Category:", "{{DEFAULTSORT", "{{Short description", "{{Use mdy dates", "{{Use dmy dates")):
            continue

        if not line.strip():
            for item in flush():
                yield item
            continue

        buf.append(line)

    for item in flush():
        yield item


def _strip_wikitext(para_wikitext: str) -> str:
    # Use mwparserfromhell when available (installed with pywikibot), otherwise fallback.
    # First, normalize a small allowlist of separator templates so we don't collapse tokens.
    wt = para_wikitext
    for pat in SEP_TEMPLATES:
        wt = pat.sub(" - ", wt)
    try:
        import mwparserfromhell  # type: ignore

        code = mwparserfromhell.parse(wt)
        return str(code.strip_code())
    except Exception:
        # Basic fallback: drop templates and refs crudely.
        text = re.sub(r"\{\{.*?\}\}", "", wt, flags=re.DOTALL)
        text = re.sub(r"<ref[^>]*>.*?</ref>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<ref[^/]*/>", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]", r"\1", text)
        return text


def _protect_abbrevs(text: str) -> Tuple[str, Dict[str, str]]:
    repl: Dict[str, str] = {}
    out = text
    for i, ab in enumerate(sorted(ABBREV_TOKENS, key=len, reverse=True), start=1):
        if ab not in out:
            continue
        token = f"__ABBR{i}__"
        repl[token] = ab
        out = out.replace(ab, token)
    return out, repl


def _restore_abbrevs(text: str, repl: Dict[str, str]) -> str:
    out = text
    for token, ab in repl.items():
        out = out.replace(token, ab)
    return out


def _split_sentences(plain: str) -> List[str]:
    """Deterministic sentence splitting with basic abbreviation protection."""
    protected, repl = _protect_abbrevs(plain)
    # Protect middle initials in names (e.g., "George W. Bush") so we don't split at "W."
    protected = re.sub(r"\b([A-Z])\.(?=\s+[A-Z][a-z])", r"\1__INITDOT__", protected)
    parts = [s.strip() for s in re.split(r"(?<=[.?!])\s+", protected) if s.strip()]
    out = []
    for p in parts:
        p = p.replace("__INITDOT__", ".")
        out.append(_restore_abbrevs(p, repl))
    return out


def _cleanup_sentence_text(sentence: str) -> str:
    s = str(sentence or "")
    # Recover spacing in common citation joins (e.g. "exam.Rutenberg")
    s = re.sub(r"([a-z0-9])([.!?])([A-Z])", r"\1\2 \3", s)
    s = re.sub(r",([A-Z])", r", \1", s)
    s = _collapse_ws(s)

    # Drop trailing author/date reference tails.
    for pat in CITATION_TAIL_RE:
        s2 = pat.sub("", s).strip()
        if s2 != s:
            s = s2
    return _collapse_ws(s)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Extract date-anchored timeline candidates from a wiki snapshot.")
    ap.add_argument("--snapshot", type=Path, required=True, help="Path to snapshot JSON (from wiki_pull_api.py)")
    ap.add_argument(
        "--out",
        type=Path,
        default=Path("SensibLaw/.cache_local/wiki_timeline_gwb.json"),
        help="Output JSON path (gitignored).",
    )
    ap.add_argument("--max-events", type=int, default=220, help="Max timeline candidates to emit (default: 220)")
    ap.add_argument(
        "--section-contains",
        action="append",
        default=[],
        help="Only include paragraphs where section contains this substring (repeatable).",
    )
    args = ap.parse_args(argv)

    snap = _load_snapshot(args.snapshot)
    wikitext = snap.get("wikitext") or ""
    if not isinstance(wikitext, str) or not wikitext.strip():
        raise SystemExit("snapshot has no wikitext; re-run wiki_pull_api.py without --no-wikitext")

    section_filters = [s.lower() for s in (args.section_contains or []) if s and s.strip()]

    events: List[dict] = []
    idx = 0
    for section, para_wt in _iter_section_paragraphs(wikitext):
        if section_filters:
            sec = section.lower()
            if not any(f in sec for f in section_filters):
                continue

        plain = _strip_wikitext(para_wt)
        plain = _collapse_ws(_strip_refs(plain))
        if not plain:
            continue

        # Split into "sentences" conservatively; protect common abbreviations.
        # We want a stable, curation-friendly unit, not perfect NLP.
        sentences = _split_sentences(plain)

        for s in sentences:
            s = _cleanup_sentence_text(s)
            if not s:
                continue
            anchor = _parse_anchor(s)
            if not anchor:
                continue
            idx += 1
            # Sentence-local link capture reduces irrelevant paragraph links.
            links = _links_in_sentence(para_wt, s)
            para_links = _wikitext_links(para_wt)
            events.append(
                {
                    "event_id": f"ev:{idx:04d}",
                    "anchor": anchor.to_json(),
                    "section": section,
                    "text": s,
                    "links": links[:50],
                    "links_para": para_links[:120],
                }
            )
            if len(events) >= int(args.max_events):
                break
        if len(events) >= int(args.max_events):
            break

    out = {
        "ok": True,
        "generated_at": _utc_now_iso(),
        "snapshot": {
            "path": str(args.snapshot),
            "wiki": snap.get("wiki"),
            "title": snap.get("title"),
            "revid": snap.get("revid"),
            "rev_timestamp": snap.get("rev_timestamp"),
            "source_url": snap.get("source_url"),
        },
        "filters": {
            "section_contains": section_filters,
        },
        "events": events,
        "notes": [
            "This is a non-authoritative timeline substrate extracted from Wikipedia prose.",
            "Anchors are explicit (month/day) or weak (year-only) and are not causal claims.",
            "Links are identity glue only and do not imply inclusion in any investigative graph.",
        ],
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(args.out), "events": len(events)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
