#!/usr/bin/env python3
"""GWB review CLI over the single PostgreSQL semantic spine."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.fact_intake.postgres_runtime import require_postgres_runtime_configuration
from src.policy.corpus_compilation import default_compiler_context
from src.policy.fibred_operational_corpus_compilation import compile_document_fibred_operational
from src.policy.follow_projection_compat import project_gwb_follow_surface
from src.policy.postgres_semantic_spine import GWB_REVIEW_PROFILE, run_postgres_semantic_spine


def _connect(database_url: str):
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("GWB review requires psycopg and PostgreSQL") from exc
    return psycopg.connect(database_url)


def _compile(document_input: Mapping[str, Any]) -> Mapping[str, Any]:
    compilation = compile_document_fibred_operational(
        document_input,
        default_compiler_context(),
        closure_workers=4,
        owner_partitions=8,
    )
    return {"artifacts": compilation.artifacts}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build GWB review surfaces through the PostgreSQL semantic spine."
    )
    parser.add_argument(
        "--database-url", default=os.environ.get("DATABASE_URL", "")
    )
    parser.add_argument("--source-path", type=Path, required=True)
    parser.add_argument("--document-ref", default="")
    parser.add_argument("--source-ref", default="")
    parser.add_argument("--command", choices=("run", "bundle", "report"), default="run")
    args = parser.parse_args(argv)

    database_url = require_postgres_runtime_configuration(
        {"database_url": args.database_url}
    )
    path = args.source_path.resolve()
    text = path.read_text(encoding="utf-8")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    document_ref = args.document_ref or f"document:{digest}"
    document_input = {
        "document_ref": document_ref,
        "source_ref": args.source_ref or f"source:file:{path}",
        "media_type": "text/plain",
        "canonical_text": text,
        "content_sha256": digest,
        "scope_ref": document_ref,
    }
    with _connect(database_url) as connection:
        result = run_postgres_semantic_spine(
            connection=connection,
            document_input=document_input,
            compile_document=_compile,
            profile=GWB_REVIEW_PROFILE,
        )
    surface = project_gwb_follow_surface(result.follow_projection)
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
            "binding_edge_count": len(surface["binding_edges"]),
            "reference_argument_factor_count": len(
                result.artifacts.get("pronominal_argument_factor_refs") or ()
            ),
            "runtime_receipt": result.receipt.to_dict(),
        }
    else:
        output = result.receipt.to_dict()
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
