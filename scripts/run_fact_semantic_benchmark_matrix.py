#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_SENSIBLAW_ROOT = _THIS_DIR.parent
if str(_SENSIBLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(_SENSIBLAW_ROOT))

from scripts.benchmark_fact_semantics import main as benchmark_main


def _load_manifest(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the fact semantic benchmark matrix from a corpus manifest.")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("tests/fixtures/fact_semantic_bench/corpus_manifest.json"),
        help="Path to the benchmark corpus manifest.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".cache_local/fact_semantic_bench"),
        help="Directory where per-run JSON reports will be written.",
    )
    parser.add_argument(
        "--max-tier",
        type=int,
        default=None,
        help="Optional maximum tier size to run.",
    )
    parser.add_argument(
        "--corpus-id",
        action="append",
        default=[],
        help="Optional corpus_id to run. Repeatable.",
    )
    args = parser.parse_args(argv)

    manifest = _load_manifest(args.manifest)
    corpus_rows = manifest.get("corpora")
    if not isinstance(corpus_rows, list) or not corpus_rows:
        raise SystemExit(f"Manifest has no corpora: {args.manifest}")

    selected = {str(value) for value in args.corpus_id if str(value).strip()}
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    started = time.strftime("%Y%m%dT%H%M%S")
    results: list[dict[str, object]] = []
    for row in corpus_rows:
        if not isinstance(row, dict):
            continue
        corpus_id = str(row.get("corpus_id") or "").strip()
        if not corpus_id:
            continue
        if selected and corpus_id not in selected:
            continue
        corpus_path = Path(str(row.get("path") or ""))
        tiers = row.get("tiers")
        if not isinstance(tiers, list):
            continue
        for tier in tiers:
            count = int(tier)
            if args.max_tier is not None and count > args.max_tier:
                continue
            report_path = output_dir / f"{started}_{corpus_id}_{count}.json"
            with tempfile.TemporaryDirectory(prefix=f"bench-{corpus_id}-{count}-") as tmpdir:
                db_path = Path(tmpdir) / "bench.sqlite"
                original_stdout = sys.stdout
                try:
                    from io import StringIO

                    capture = StringIO()
                    sys.stdout = capture
                    exit_code = benchmark_main(
                        [
                            "--corpus-file",
                            str(corpus_path),
                            "--count",
                            str(count),
                            "--db-path",
                            str(db_path),
                        ]
                    )
                finally:
                    sys.stdout = original_stdout
                output = capture.getvalue().strip()
                payload = json.loads(output) if output else {}
                payload["exit_code"] = exit_code
                payload["corpus_id"] = corpus_id
                payload["manifest_path"] = str(args.manifest)
                report_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                results.append(
                    {
                        "corpus_id": corpus_id,
                        "count": count,
                        "exit_code": exit_code,
                        "report_path": str(report_path),
                        "elapsed_ms": payload.get("elapsed_ms"),
                        "refresh_status": ((payload.get("refresh") or {}).get("refresh_status") if isinstance(payload.get("refresh"), dict) else None),
                    }
                )
                print(
                    f"[bench-matrix] corpus={corpus_id} count={count} exit={exit_code} "
                    f"status={results[-1]['refresh_status']} report={report_path}"
                )

    summary = {
        "manifest": str(args.manifest),
        "output_dir": str(output_dir),
        "run_count": len(results),
        "results": results,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
