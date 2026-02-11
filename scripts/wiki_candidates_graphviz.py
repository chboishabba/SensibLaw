#!/usr/bin/env python3
"""Render a Graphviz graph from wiki candidate artifacts.

Goal: visualize the raw candidate set (including event-heavy skew) before any
trimming, so we can debug extraction behavior without committing to a graph
schema or ontology decisions.

Input:
- `SensibLaw/.cache_local/wiki_candidates_*.json` (from wiki_candidates_extract.py)

Output (gitignored):
- `.dot` always
- `.svg` optionally, if Graphviz `dot` exists and `--render-svg` is set
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def _slug(s: str) -> str:
    return s.replace("\\", "_").replace('"', "'")


def _dot_quote(s: str) -> str:
    return '"' + _slug(s) + '"'


def _read_candidates(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _edge_key(src: str, dst: str) -> Tuple[str, str]:
    return (src, dst)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Render Graphviz dot for wiki candidates.")
    ap.add_argument(
        "--in",
        dest="in_path",
        type=Path,
        default=Path("SensibLaw/.cache_local/wiki_candidates_gwb.json"),
        help="Input candidates JSON (default: %(default)s)",
    )
    ap.add_argument(
        "--out-dot",
        dest="out_dot",
        type=Path,
        default=Path("SensibLaw/.cache_local/wiki_candidates_gwb.dot"),
        help="Output dot path (default: %(default)s)",
    )
    ap.add_argument(
        "--render-svg",
        action="store_true",
        help="Also render SVG via Graphviz `dot` if available.",
    )
    ap.add_argument(
        "--out-svg",
        dest="out_svg",
        type=Path,
        default=Path("SensibLaw/.cache_local/wiki_candidates_gwb.svg"),
        help="Output svg path (default: %(default)s)",
    )
    ap.add_argument(
        "--limit",
        type=int,
        default=180,
        help="Max candidate nodes to include (default: 180; >=162 includes all current GWB set).",
    )
    ap.add_argument(
        "--min-evidence",
        type=int,
        default=1,
        help="Only include candidates with >= N evidence pages (default: 1).",
    )
    args = ap.parse_args(argv)

    data = _read_candidates(args.in_path)
    rows = data.get("rows") or []
    if not isinstance(rows, list):
        raise SystemExit("invalid input: expected rows[]")

    # Build page hubs from evidence.
    page_nodes: Dict[str, dict] = {}
    edge_weights: Dict[Tuple[str, str], int] = defaultdict(int)

    # Sort by score desc (already in extractor, but don't assume).
    def _score(row: dict) -> int:
        try:
            return int(row.get("score") or 0)
        except Exception:
            return 0

    rows_sorted = sorted([r for r in rows if isinstance(r, dict)], key=_score, reverse=True)

    kept = 0
    for row in rows_sorted:
        if kept >= int(args.limit):
            break
        title = str(row.get("title") or "").strip()
        if not title:
            continue
        evidence = row.get("evidence") or []
        if not isinstance(evidence, list):
            evidence = []
        # Dedup evidence by page title.
        pages = []
        for ev in evidence:
            if not isinstance(ev, dict):
                continue
            pt = str(ev.get("page_title") or "").strip()
            if pt and pt not in pages:
                pages.append(pt)
                page_nodes[pt] = {
                    "wiki": ev.get("wiki"),
                    "page_revid": ev.get("page_revid"),
                }

        if len(pages) < int(args.min_evidence):
            continue

        for pt in pages:
            edge_weights[_edge_key(pt, title)] += 1

        kept += 1

    # Emit DOT.
    args.out_dot.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = []
    lines.append("digraph wiki_candidates {")
    lines.append('  graph [rankdir="LR", bgcolor="white"];')
    lines.append('  node [fontname="Helvetica", fontsize=10, shape="box"];')
    lines.append('  edge [color="#777777"];')
    lines.append("")
    lines.append("  // Page hubs")
    lines.append('  node [shape="folder", style="filled", fillcolor="#e8f4ff"];')
    for pt in sorted(page_nodes.keys()):
        lines.append(f"  {_dot_quote('page:' + pt)} [label={_dot_quote(pt)}];")
    lines.append("")
    lines.append("  // Candidate titles")
    lines.append('  node [shape="box", style="filled", fillcolor="#f6f6f6"];')

    # Candidate nodes appear as edge destinations; list them once.
    candidate_titles = sorted({dst for (_, dst) in edge_weights.keys()})
    for t in candidate_titles:
        lines.append(f"  {_dot_quote('cand:' + t)} [label={_dot_quote(t)}];")

    lines.append("")
    lines.append("  // Evidence edges (page -> candidate)")
    for (src, dst), w in sorted(edge_weights.items(), key=lambda x: (-x[1], x[0][0], x[0][1])):
        # Map weights to a small penwidth range.
        pen = 1.0 + min(3.0, float(w) - 1.0)
        lines.append(
            f"  {_dot_quote('page:' + src)} -> {_dot_quote('cand:' + dst)} "
            f'[penwidth={pen:.1f}];'
        )

    lines.append("}")
    args.out_dot.write_text("\n".join(lines) + "\n", encoding="utf-8")

    rendered_svg = False
    if args.render_svg:
        dot = shutil.which("dot")
        if not dot:
            print(json.dumps({"ok": True, "dot": str(args.out_dot), "svg": None, "note": "graphviz_dot_not_found"}))
            return 0
        args.out_svg.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([dot, "-Tsvg", str(args.out_dot), "-o", str(args.out_svg)], check=False)
        rendered_svg = args.out_svg.exists() and args.out_svg.stat().st_size > 0

    print(
        json.dumps(
            {"ok": True, "dot": str(args.out_dot), "svg": str(args.out_svg) if rendered_svg else None},
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

