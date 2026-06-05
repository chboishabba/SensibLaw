from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.code_observer import observe_paths


def handle_observe(args: argparse.Namespace) -> None:
    rows = observe_paths(
        args.root,
        include_globs=args.include_glob,
        exclude_globs=args.exclude_glob,
        projection_boundary=args.projection_boundary,
        bounded_absence_target=args.bounded_absence_target,
    )
    text = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("code-observer", help="Emit evidence-only code observations")
    code_sub = parser.add_subparsers(dest="code_observer_command", required=True)
    observe = code_sub.add_parser("observe", help="Scan source files with Tree-sitter Python bindings")
    observe.add_argument("--root", type=Path, default=Path("."))
    observe.add_argument("--include-glob", action="append")
    observe.add_argument("--exclude-glob", action="append")
    observe.add_argument("--projection-boundary", action="append")
    observe.add_argument("--bounded-absence-target")
    observe.add_argument("--output", "-o", type=Path)
    observe.set_defaults(func=handle_observe)
