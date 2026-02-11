#!/usr/bin/env python3
"""Generate a bounded DBpedia lookup queue from `wiki_candidates_*.json`.

This is a curation-time artifact generator, not an ingest pipeline:
- input: `SensibLaw/.cache_local/wiki_candidates_gwb.json` (gitignored)
- output: `SensibLaw/.cache_local/dbpedia_lookup_queue_*.json` (gitignored)

Non-goals:
- no crawling
- no recursion
- no claims about truth or relevance

Contract:
- DBpedia resolution does not imply inclusion in any investigative graph.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple


DEFAULT_EXCLUDE_RE = re.compile(
    r"^(?:\d{3,4}\b)"
    r"|\b(election|convention|debates|State of the Union|invasion)\b"
    r"|\b(compound|doctrine|badge)\b"
    r"|^Bibliography of\b"
    r"|^Template\b"
    r"|^Template talk:\b",
    re.IGNORECASE,
)

NON_PERSON_KEYWORDS = re.compile(
    r"\b(Badge|Guard|Air National Guard|Research Service|Doctrine|School|University|News|Press|Service)\b",
    re.IGNORECASE,
)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def _norm_rank(score: int, max_score: int) -> float:
    if max_score <= 0:
        return 0.0
    return max(0.0, min(1.0, float(score) / float(max_score)))


def _guess_kind(title: str) -> Tuple[str, List[str]]:
    t = title.strip()
    why: List[str] = []

    # Common false positive: generic "X of Y" constructions are not people.
    if NON_PERSON_KEYWORDS.search(t):
        why.append("pattern:non_person_keyword")
        # fall through: we still allow later rules (e.g. government bodies) to tag institutions.

    # High-signal structural patterns.
    if t.startswith("Office of "):
        why.append("pattern:office_of")
        return "office", why
    if t.startswith("Department of "):
        why.append("pattern:department_of")
        return "institution", why
    if NON_PERSON_KEYWORDS.search(t):
        why.append("pattern:institution_keyword")
        return "institution", why
    if t.endswith(" Act") or t.endswith(" Act of 2001") or t.endswith(" Act of 2002"):
        why.append("pattern:act_suffix")
        return "law", why
    if "Authorization for Use of Military Force" in t:
        why.append("pattern:aumf")
        return "law", why
    if "Convention" in t or "Treaty" in t:
        why.append("pattern:treaty_or_convention")
        return "treaty", why
    if "Court" in t or "Senate" in t or "House of Representatives" in t or "Congress" in t:
        why.append("pattern:government_body")
        return "institution", why

    # Person-ish heuristic: two or more capitalized tokens, no leading year.
    if (
        re.fullmatch(r"[A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){1,4}", t)
        and "pattern:non_person_keyword" not in why
    ):
        why.append("pattern:person_name_like")
        return "person", why

    if "pattern:non_person_keyword" in why:
        return "other", why

    return "other", why or ["fallback:other"]


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Generate a DBpedia lookup queue from wiki candidates JSON.")
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
        default=Path("SensibLaw/.cache_local/dbpedia_lookup_queue_gwb.json"),
        help="Output queue JSON (default: %(default)s)",
    )
    ap.add_argument("--top-n", type=int, default=50, help="Max queued candidates (default: 50)")
    ap.add_argument(
        "--include-kinds",
        default="person,office,institution,law,treaty,program,location",
        help="Comma-separated allowlist of category_guess values to queue.",
    )
    ap.add_argument(
        "--exclude-re",
        default=DEFAULT_EXCLUDE_RE.pattern,
        help="Regex for titles to exclude (default excludes elections/conventions/debates/invasion).",
    )
    args = ap.parse_args(argv)

    in_path: Path = args.in_path
    if not in_path.exists():
        raise SystemExit(f"input not found: {in_path}")

    payload = json.loads(in_path.read_text(encoding="utf-8"))
    rows = payload.get("rows") or []
    if not isinstance(rows, list):
        raise SystemExit("invalid input: expected rows[]")

    allow = {k.strip() for k in str(args.include_kinds).split(",") if k.strip()}
    exclude_re = re.compile(str(args.exclude_re), re.IGNORECASE)

    scored: List[Tuple[int, str]] = []
    row_by_title: Dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip()
        if not title:
            continue
        score = int(row.get("score") or 0)
        row_by_title[title] = row
        scored.append((score, title))

    scored.sort(reverse=True)
    max_score = scored[0][0] if scored else 0

    candidates: List[dict] = []
    heuristics: List[str] = [
        "top_n by score (weighted link frequency)",
        "exclude regex (events/maintenance-heavy titles)",
        "kind guess by title patterns (non-authoritative)",
        "allowlist of kinds for queueing",
        "no recursion; no inferred relevance",
        "DBpedia resolution does not imply inclusion in any investigative graph"
    ]

    for score, title in scored:
        if len(candidates) >= int(args.top_n):
            break
        if exclude_re.search(title):
            continue
        kind, why = _guess_kind(title)
        if kind not in allow:
            continue

        candidates.append(
            {
                "title": title,
                "score": int(score),
                "rank": _norm_rank(int(score), int(max_score)),
                "category_guess": kind,
                "rationale": why,
                "status": "pending",
                "dbpedia": None,
                "notes": "",
            }
        )

    out = {
        "queue_id": f"dbpedia_queue_{in_path.stem}",
        "generated_at": _utc_now_iso(),
        "source": {
            "input_file": str(in_path),
            "input_sha256": _sha256_file(in_path),
            "note": "Generated from wiki candidates; DBpedia URIs are identity glue, not evidence.",
        },
        "selection_policy": {
            "top_n": int(args.top_n),
            "heuristics": heuristics,
            "excludes": [str(args.exclude_re)],
        },
        "candidates": candidates,
    }

    args.out_path.parent.mkdir(parents=True, exist_ok=True)
    args.out_path.write_text(json.dumps(out, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(args.out_path), "queued": len(candidates)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
