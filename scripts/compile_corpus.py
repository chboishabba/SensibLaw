"""Run the generic local-only directory compilation kernel."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.policy.corpus_compilation import (  # noqa: E402
    CompilerContext,
    compile_directory,
    default_compiler_context,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--context", type=Path)
    parser.add_argument(
        "--phase", choices=("inventory", "local", "demand_planning"), default="local"
    )
    parser.add_argument("--no-recursive", action="store_true")
    parser.add_argument("--max-files", type=int)
    parser.add_argument("--max-file-bytes", type=int)
    parser.add_argument("--max-total-bytes", type=int)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    context = default_compiler_context()
    if args.context:
        context = CompilerContext.from_mapping(
            json.loads(args.context.read_text(encoding="utf-8"))
        )
    result = compile_directory(
        args.input_dir,
        context=context,
        output_store=args.output,
        recursive=not args.no_recursive,
        max_files=args.max_files,
        max_file_bytes=args.max_file_bytes,
        max_total_bytes=args.max_total_bytes,
        execution_phase=args.phase,
    )
    print(
        json.dumps(
            result["summary"] if "summary" in result else result["manifest"],
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
