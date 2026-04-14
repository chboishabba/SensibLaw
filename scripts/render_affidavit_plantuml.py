#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
from typing import Any

_THIS_DIR = Path(__file__).resolve().parent
_SENSIBLAW_ROOT = _THIS_DIR.parent
if str(_SENSIBLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(_SENSIBLAW_ROOT))

from src.fact_intake import build_contested_affidavit_review_summary
from src.reporting.affidavit_plantuml import (
    build_affidavit_mechanical_plantuml,
    build_affidavit_resolution_plantuml,
)


def _load_payload(*, artifact_json: Path | None, db_path: Path | None, review_run_id: str | None) -> dict[str, Any]:
    if artifact_json is not None:
        return json.loads(artifact_json.read_text(encoding="utf-8"))
    if db_path is not None and review_run_id:
        with sqlite3.connect(str(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            return build_contested_affidavit_review_summary(conn, review_run_id=review_run_id)
    raise SystemExit("provide either --artifact-json or both --db-path and --review-run-id")


def _render_svg(paths: list[Path]) -> list[Path]:
    plantuml = shutil.which("plantuml")
    if not plantuml:
        raise SystemExit("plantuml executable not found")
    subprocess.run([plantuml, "-tsvg", *[str(path) for path in paths]], check=True)
    return [path.with_suffix(".svg") for path in paths]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render semantic and mechanical PlantUML views from a contested affidavit review payload.")
    parser.add_argument("--artifact-json", type=Path, default=None, help="Coverage-review JSON artifact to render.")
    parser.add_argument("--db-path", type=Path, default=None, help="Optional sqlite path for persisted contested-review runs.")
    parser.add_argument("--review-run-id", default=None, help="Persisted contested-review run id when using --db-path.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory to write PlantUML artifacts into.")
    parser.add_argument("--stem", default="affidavit_claim_graph", help="Output file stem.")
    parser.add_argument("--title-prefix", default="Affidavit", help="Title prefix for rendered diagrams.")
    parser.add_argument("--max-claims", type=int, default=None, help="Optional limit on the number of claims rendered.")
    parser.add_argument("--token-limit", type=int, default=10, help="Max lexical atoms shown per claim in the mechanical view.")
    parser.add_argument("--render-svg", action="store_true", help="Also render SVG outputs through PlantUML.")
    args = parser.parse_args(argv)

    payload = _load_payload(
        artifact_json=args.artifact_json.resolve() if args.artifact_json else None,
        db_path=args.db_path.resolve() if args.db_path else None,
        review_run_id=args.review_run_id,
    )

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = str(args.stem).strip() or "affidavit_claim_graph"

    resolution_path = output_dir / f"{stem}.resolution.puml"
    mechanical_path = output_dir / f"{stem}.mechanical.puml"

    resolution_path.write_text(
        build_affidavit_resolution_plantuml(
            payload,
            title=f"{args.title_prefix} Claim Resolution Graph",
            max_claims=args.max_claims,
        ),
        encoding="utf-8",
    )
    mechanical_path.write_text(
        build_affidavit_mechanical_plantuml(
            payload,
            title=f"{args.title_prefix} Mechanical Parse Graph",
            max_claims=args.max_claims,
            token_limit=args.token_limit,
        ),
        encoding="utf-8",
    )

    svg_paths: list[Path] = []
    if args.render_svg:
        svg_paths = _render_svg([resolution_path, mechanical_path])

    print(
        json.dumps(
            {
                "ok": True,
                "resolution_puml": str(resolution_path),
                "mechanical_puml": str(mechanical_path),
                "svg_paths": [str(path) for path in svg_paths],
                "claim_count": len(payload.get("affidavit_rows") or []),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
