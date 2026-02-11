#!/usr/bin/env python3
"""Report distribution of wiki candidate titles by coarse heuristic categories.

This is a curation-time analysis helper to detect dominance/pathologies, e.g.:
- person-heavy skew
- events dominating
- maintenance/meta leakage

It does not alter any stored artifacts. It writes a small JSON report.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple


NON_PERSON_KEYWORDS = re.compile(
    r"\b(Badge|Guard|Air National Guard|Research Service|Doctrine|School|University|News|Press|Service)\b",
    re.IGNORECASE,
)


def _utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def _guess_kind(title: str) -> str:
    t = title.strip()
    if not t:
        return "other"
    if t.startswith("Category:") or t.startswith("Template") or t.startswith("Wikipedia:"):
        return "other"
    if re.match(r"^\d{3,4}\b", t):
        return "event"
    if re.search(r"\b(election|convention|debates|State of the Union|invasion|war)\b", t, re.IGNORECASE):
        return "event"
    if t.startswith("Office of "):
        return "office"
    if t.startswith("Department of "):
        return "institution"
    if t.endswith(" Act") or "Authorization for Use of Military Force" in t:
        return "law"
    if "Convention" in t or "Treaty" in t:
        return "treaty"
    if "Court" in t or "Senate" in t or "House of Representatives" in t or "Congress" in t:
        return "institution"
    if NON_PERSON_KEYWORDS.search(t):
        return "institution"
    if re.fullmatch(r"[A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){1,4}", t):
        return "person"
    return "other"


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Report coarse distribution for wiki candidates JSON.")
    ap.add_argument(
        "--in",
        dest="in_path",
        type=Path,
        default=Path("SensibLaw/.cache_local/wiki_candidates_gwb.json"),
        help="Input candidates JSON (default: %(default)s)",
    )
    ap.add_argument(
        "--out",
        dest="out_path",
        type=Path,
        default=Path("SensibLaw/.cache_local/wiki_candidates_gwb_distribution.json"),
        help="Output report JSON (default: %(default)s)",
    )
    ap.add_argument("--top-k-samples", type=int, default=12, help="Top samples per kind (default: 12)")
    args = ap.parse_args(argv)

    payload = json.loads(args.in_path.read_text(encoding="utf-8"))
    rows = payload.get("rows") or []
    if not isinstance(rows, list):
        raise SystemExit("invalid input: expected rows[]")

    counts = Counter()
    samples: Dict[str, List[dict]] = {}

    for row in rows:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip()
        if not title:
            continue
        score = int(row.get("score") or 0)
        kind = _guess_kind(title)
        counts[kind] += 1
        bucket = samples.setdefault(kind, [])
        # Keep best-scoring samples.
        bucket.append({"title": title, "score": score})

    for kind, bucket in samples.items():
        bucket.sort(key=lambda x: int(x.get("score") or 0), reverse=True)
        samples[kind] = bucket[: max(1, int(args.top_k_samples))]

    out = {
        "ok": True,
        "generated_at": _utc_now_iso(),
        "input": str(args.in_path),
        "total_candidates": int(sum(counts.values())),
        "distribution": dict(counts),
        "top_samples": samples,
        "notes": [
            "This report is heuristic-only and non-authoritative.",
            "Use it to detect dominance/pathologies before building any graph.",
        ],
    }

    args.out_path.parent.mkdir(parents=True, exist_ok=True)
    args.out_path.write_text(json.dumps(out, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(args.out_path), "total": out["total_candidates"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

