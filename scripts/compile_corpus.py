"""Compile a bounded corpus into the generic PostgreSQL runtime."""

from __future__ import annotations

import argparse
import json
import os
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
from src.policy.postgres_corpus_compilation import compile_directory_postgres  # noqa: E402
from src.storage.postgres import PostgresCompilerStore  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--context", type=Path)
    parser.add_argument(
        "--phase", choices=("inventory", "local", "demand_planning"), default="local"
    )
    parser.add_argument("--no-recursive", action="store_true")
    parser.add_argument("--max-files", type=int)
    parser.add_argument("--max-file-bytes", type=int)
    parser.add_argument("--max-total-bytes", type=int)
    parser.add_argument(
        "--emit-legacy-json",
        type=Path,
        metavar="OUTPUT_DIR",
        help="Explicit compatibility export; PostgreSQL remains authoritative.",
    )
    args = parser.parse_args()
    if not args.database_url and not args.emit_legacy_json:
        parser.error("--database-url or DATABASE_URL is required")
    return args


def main() -> int:
    args = _parse_args()
    context = default_compiler_context()
    if args.context:
        context = CompilerContext.from_mapping(
            json.loads(args.context.read_text(encoding="utf-8"))
        )
    common = {
        "recursive": not args.no_recursive,
        "max_files": args.max_files,
        "max_file_bytes": args.max_file_bytes,
        "max_total_bytes": args.max_total_bytes,
        "execution_phase": args.phase,
    }
    if args.database_url:
        store = PostgresCompilerStore.connect(args.database_url)
        try:
            result = compile_directory_postgres(
                args.input_dir,
                context=context,
                store=store,
                **common,
            )
        finally:
            store.close()
        print(f"corpus_ref={result.corpus_ref}")
        print(f"documents={len(result.document_refs)}")
        print(f"open_demands={len(result.demand_refs)}")
        print(f"failures={len(result.failure_refs)}")
    if args.emit_legacy_json:
        compile_directory(
            args.input_dir,
            context=context,
            output_store=args.emit_legacy_json,
            **common,
        )
        print(f"legacy_json_export={args.emit_legacy_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
