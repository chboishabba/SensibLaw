#!/usr/bin/env python3
"""AU fact-review CLI over the single PostgreSQL semantic spine.

SQLite is deprecated as a runtime. Historical SQLite fixtures may be carried
forward only through the explicit ``import-sqlite`` command, after which normal
runtime reads and writes use PostgreSQL exclusively.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping

_THIS_DIR = Path(__file__).resolve().parent
_SENSIBLAW_ROOT = _THIS_DIR.parent
if str(_SENSIBLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(_SENSIBLAW_ROOT))

from src.fact_intake.legacy_sqlite_import import import_legacy_sqlite_fixture
from src.fact_intake.postgres_runtime import require_postgres_runtime_configuration
from src.policy.corpus_compilation import default_compiler_context
from src.policy.fibred_operational_corpus_compilation import (
    compile_document_fibred_operational,
)
from src.policy.follow_projection_compat import project_au_follow_surface
from src.policy.postgres_semantic_spine import (
    AU_FACT_REVIEW_PROFILE,
    run_postgres_semantic_spine,
)


def _connect(database_url: str):
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("AU fact review requires psycopg and PostgreSQL") from exc
    return psycopg.connect(database_url)


def _document_input(args: argparse.Namespace) -> dict[str, Any]:
    if args.source_path:
        path = Path(args.source_path).resolve()
        text = path.read_text(encoding="utf-8")
        source_ref = f"source:file:{path}"
    else:
        text = str(args.canonical_text or "")
        source_ref = str(args.source_ref or "source:au-fact-review-cli")
    if not text.strip():
        raise ValueError("provide --source-path or --canonical-text")
    document_ref = str(args.document_ref or "").strip() or (
        "document:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
    )
    return {
        "document_ref": document_ref,
        "source_ref": source_ref,
        "media_type": "text/plain",
        "canonical_text": text,
        "content_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "scope_ref": document_ref,
    }


def _compile(document_input: Mapping[str, Any]) -> Mapping[str, Any]:
    compilation = compile_document_fibred_operational(
        document_input,
        default_compiler_context(),
        closure_workers=4,
        owner_partitions=8,
    )
    return {"artifacts": compilation.artifacts}


def _legacy_import(args: argparse.Namespace, database_url: str) -> dict[str, Any]:
    if not args.sqlite_path:
        raise ValueError("import-sqlite requires --sqlite-path")

    def reject_unmapped(_connection, rows):
        # Explicitly bounded reference import: rows are inventoried and rejected
        # until a table-specific PostgreSQL mapper is declared. This preserves the
        # no-dual-authority rule and produces a complete discrepancy receipt.
        return (0, len(tuple(rows)), (), ("table-mapper-not-declared",))

    with _connect(database_url) as connection:
        receipt = import_legacy_sqlite_fixture(
            sqlite_path=args.sqlite_path,
            postgres_connection=connection,
            table_importers={name: reject_unmapped for name in args.sqlite_table},
        )
    return receipt.to_dict()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build AU fact-review surfaces through the PostgreSQL semantic spine."
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", ""),
        help="PostgreSQL connection URL; defaults to DATABASE_URL.",
    )
    parser.add_argument("--document-ref", default="")
    parser.add_argument("--source-ref", default="")
    parser.add_argument("--source-path", default="")
    parser.add_argument("--canonical-text", default="")
    parser.add_argument(
        "--sqlite-path",
        default="",
        help="Legacy fixture path; valid only with import-sqlite.",
    )
    parser.add_argument(
        "--sqlite-table",
        action="append",
        default=[],
        help="Historical SQLite table to inventory/import; repeat as needed.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run", help="Compile, persist, query, and print runtime receipt")
    sub.add_parser("bundle", help="Print detached presentation response")
    sub.add_parser("report", help="Print relational follow summary and timings")
    sub.add_parser("import-sqlite", help="Import/replay a bounded historical SQLite fixture")
    args = parser.parse_args(argv)

    database_url = require_postgres_runtime_configuration(
        {"database_url": args.database_url, "sqlite_path": ""}
    )
    if args.command == "import-sqlite":
        output = _legacy_import(args, database_url)
        print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if args.sqlite_path:
        raise ValueError(
            "--sqlite-path is accepted only by import-sqlite; SQLite cannot drive runtime"
        )

    document_input = _document_input(args)
    with _connect(database_url) as connection:
        result = run_postgres_semantic_spine(
            connection=connection,
            document_input=document_input,
            compile_document=_compile,
            profile=AU_FACT_REVIEW_PROFILE,
        )

    surface = project_au_follow_surface(result.follow_projection)
    if args.command == "bundle":
        output: dict[str, Any] = {
            **surface,
            "runtime_receipt": result.receipt.to_dict(),
        }
    elif args.command == "report":
        output = {
            "document_ref": result.receipt.document_ref,
            "projection_ref": result.receipt.projection_ref,
            "summary": surface["summary"],
            "runtime_receipt": result.receipt.to_dict(),
            "projection_demands": list(
                result.artifacts.get("projection_demands") or ()
            ),
            "legal_ir_projected": sum(
                1
                for row in result.artifacts.get("domain_ir_projections") or ()
                if str(row.get("domain") or "") == "legal"
            ),
            "zero_legal_ir_is_valid_when_authority_absent": True,
        }
    else:
        output = result.receipt.to_dict()
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
