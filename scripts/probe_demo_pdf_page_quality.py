#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


_THIS_DIR = Path(__file__).resolve().parent
_SENSIBLAW_ROOT = _THIS_DIR.parent
if str(_SENSIBLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(_SENSIBLAW_ROOT))

from src.pdf_ingest import extract_pdf_text


_TERMINAL_PUNCTUATION_RE = re.compile(r"[.!?:;][\"')\\]]*$")


def _collapse_ws(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _word_count(text: str) -> int:
    return len([token for token in text.split(" ") if token.strip()])


def _starts_with_lower(text: str) -> bool:
    stripped = text.lstrip()
    return bool(stripped) and stripped[0].islower()


def _terminal_closed(text: str) -> bool:
    stripped = text.rstrip()
    if not stripped:
        return True
    return bool(_TERMINAL_PUNCTUATION_RE.search(stripped))


def build_page_quality_probe(pages: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    normalized_pages = []
    heading_counts: dict[str, int] = {}

    for raw_page in pages:
        heading = _collapse_ws(raw_page.get("heading"))
        body = _collapse_ws(raw_page.get("text"))
        lines = raw_page.get("lines") or ()
        page_number = int(raw_page.get("page") or (len(normalized_pages) + 1))
        normalized_pages.append(
            {
                "page": page_number,
                "heading": heading,
                "body": body,
                "line_count": len(list(lines)),
                "heading_word_count": _word_count(heading),
                "body_word_count": _word_count(body),
                "heading_char_count": len(heading),
                "body_char_count": len(body),
            }
        )
        if heading:
            heading_counts[heading] = heading_counts.get(heading, 0) + 1

    page_reports = []
    for page in normalized_pages:
        heading = page["heading"]
        page_reports.append(
            {
                **page,
                "heading_repeated": bool(heading) and heading_counts.get(heading, 0) > 1,
                "body_present": page["body_char_count"] > 0,
            }
        )

    boundary_reports = []
    for previous, current in zip(page_reports, page_reports[1:]):
        boundary_reports.append(
            {
                "previous_page": previous["page"],
                "next_page": current["page"],
                "same_heading": previous["heading"] == current["heading"] and bool(previous["heading"]),
                "previous_terminal_closed": _terminal_closed(previous["body"]),
                "next_starts_lower": _starts_with_lower(current["body"]),
                "continuation_candidate": (
                    not _terminal_closed(previous["body"])
                    and _starts_with_lower(current["body"])
                ),
            }
        )

    return {
        "page_count": len(page_reports),
        "pages_with_body": sum(1 for page in page_reports if page["body_present"]),
        "repeated_heading_pages": sum(1 for page in page_reports if page["heading_repeated"]),
        "continuation_candidate_count": sum(
            1 for boundary in boundary_reports if boundary["continuation_candidate"]
        ),
        "page_reports": page_reports,
        "boundary_reports": boundary_reports,
    }


def probe_pdf_page_quality(pdf_path: Path) -> dict[str, Any]:
    pages = list(extract_pdf_text(pdf_path))
    report = build_page_quality_probe(pages)
    report["pdf"] = str(pdf_path)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Emit bounded structural page-quality probes for a PDF ingest candidate."
    )
    parser.add_argument("pdf", type=Path, help="PDF path to inspect.")
    args = parser.parse_args()
    report = probe_pdf_page_quality(args.pdf)
    json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
