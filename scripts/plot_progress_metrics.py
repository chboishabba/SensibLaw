#!/usr/bin/env python3
"""Render progress-rate and stage-timeline graphs from a completed phase ledger."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.runtime.progress_plot import load_progress_ledger, render_progress_plots


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "progress_json",
        type=Path,
        help="PhaseRecorder JSON, for example local_pnf_compile_progress.json.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Destination directory. Defaults to <progress stem>_plots beside the input.",
    )
    parser.add_argument(
        "--format",
        dest="formats",
        action="append",
        choices=("png", "svg"),
        help="Output format; repeat to request both. Defaults to PNG and SVG.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    source = args.progress_json.resolve()
    target = (
        args.output_dir.resolve()
        if args.output_dir is not None
        else source.with_name(f"{source.stem}_plots")
    )
    manifest = render_progress_plots(
        load_progress_ledger(source),
        target,
        formats=tuple(args.formats or ("png", "svg")),
    )
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
