#!/usr/bin/env python3
"""Provision an isolated PostgreSQL authority fixture and run a B1 smoke test."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.runtime.postgres_provisioning import provision_local_postgres
from src.storage.postgres.hierarchy_diagnostic import diagnose_authored_hierarchy
from src.storage.postgres.spacy_parser_model import ParserStreamingPolicy, connect
from src.storage.postgres.streaming_spacy_execution import (
    run_streaming_spacy_execution,
)
from scripts.benchmark_sentence_paragraph_delta_transport import (
    benchmark_sentence_paragraph_delta_transport,
)


SMOKE_TEXT = (
    "The authority must preserve the record. The reviewer may inspect it.\n\n"
    "Unless an exception applies, the duty continues. The process remains open."
)


def _migration_manifest(database_url: str) -> dict[str, object]:
    migration_root = ROOT / "database" / "postgres_migrations"
    expected = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(migration_root.glob("*.sql"))
    }
    connection = connect(database_url)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute(
                    "SELECT current_database(), current_user, version()"
                )
                database, user, version = cursor.fetchone()
                cursor.execute(
                    """
                    SELECT migration_name, content_sha256
                      FROM public.sensiblaw_schema_migration
                     ORDER BY migration_name
                    """
                )
                applied = {
                    str(name): str(digest) for name, digest in cursor.fetchall()
                }
                cursor.execute(
                    """
                    SELECT tg.tgname, pg_get_triggerdef(tg.oid),
                           pg_get_functiondef(proc.oid)
                      FROM pg_trigger AS tg
                      JOIN pg_proc AS proc ON proc.oid = tg.tgfoid
                      JOIN pg_class AS rel ON rel.oid = tg.tgrelid
                      JOIN pg_namespace AS ns ON ns.oid = rel.relnamespace
                     WHERE ns.nspname = 'execution'
                       AND rel.relname = 'semantic_parser_sentence'
                       AND NOT tg.tgisinternal
                     ORDER BY tg.tgname
                    """
                )
                triggers = [
                    {
                        "name": str(name),
                        "definition": str(definition),
                        "function": str(function),
                    }
                    for name, definition, function in cursor.fetchall()
                ]
    finally:
        connection.close()
    mismatches = sorted(
        name
        for name, digest in expected.items()
        if applied.get(name) != digest
    )
    missing = sorted(set(expected) - set(applied))
    extra = sorted(set(applied) - set(expected))
    trigger_source = (
        ROOT / "database" / "postgres_migrations" / "149_setwise_sentence_region_work.sql"
    ).read_text(encoding="utf-8")
    trigger_verified = any(
        "project_numeric_sentence_regions" in row["function"]
        and "REFERENCING NEW TABLE AS inserted_sentence" in trigger_source
        and "FOR EACH STATEMENT" in row["definition"]
        for row in triggers
    )
    return {
        "database": str(database),
        "user": str(user),
        "server_version": str(version),
        "expected_migration_count": len(expected),
        "applied_migration_count": len(applied),
        "migration_hash_mismatches": mismatches,
        "missing_migrations": missing,
        "extra_migrations": extra,
        "migration_chain_verified": not mismatches and not missing and not extra,
        "sentence_producer_triggers": triggers,
        "sentence_producer_trigger_verified": trigger_verified,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--source-path", type=Path)
    parser.add_argument("--run-full", action="store_true")
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    if args.run_full and not args.source_path:
        parser.error("--run-full requires --source-path")

    certification_ref = f"b1-smoke:{uuid4().hex}"
    output_root = args.output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    receipt: dict[str, object] = {
        "contract": "sensiblaw.b1-authority-certification.v0_1",
        "certification_ref": certification_ref,
        "historical_database_mutated": False,
        "provider_io_performed": False,
        "smoke_text_sha256": hashlib.sha256(SMOKE_TEXT.encode()).hexdigest(),
    }
    try:
        isolated_url, database_name = provision_local_postgres(
            admin_url=args.database_url,
            migration_root=ROOT / "database" / "postgres_migrations",
            run_ref=certification_ref,
        )
        receipt["isolated_database"] = database_name
        receipt["migration_manifest"] = _migration_manifest(isolated_url)
        if not receipt["migration_manifest"]["migration_chain_verified"]:
            raise RuntimeError("isolated migration chain did not verify")
        if not receipt["migration_manifest"]["sentence_producer_trigger_verified"]:
            raise RuntimeError("isolated sentence producer trigger did not verify")

        run_ref = f"typed-spacy-run:{uuid4().hex}"
        document_ref = f"document:b1-smoke:{uuid4().hex}"
        carrier = run_streaming_spacy_execution(
            database_url=isolated_url,
            run_ref=run_ref,
            document_ref=document_ref,
            canonical_text=SMOKE_TEXT,
            parser_contract_ref="parser:spacy:b1-authority-smoke:v1",
            artifact_root=output_root / "parser-artifacts",
            worker_count=1,
            policy=ParserStreamingPolicy(
                target_chars=1_024,
                context_chars=64,
                batch_size=1,
                cache_docbin=False,
            ),
        )
        receipt["run_ref"] = run_ref
        receipt["document_ref"] = document_ref
        receipt["carrier"] = dict(carrier["parser_receipt"])
        receipt["hierarchy_diagnostic"] = diagnose_authored_hierarchy(
            isolated_url,
            run_ref=run_ref,
            document_ref=document_ref,
        )
        receipt["smoke_passed"] = (
            receipt["hierarchy_diagnostic"]["classification"]
            == "valid_authored_hierarchy"
        )
        if args.run_full:
            source_path = args.source_path.resolve()
            canonical_text = source_path.read_text(encoding="utf-8")
            receipt["full_source"] = {
                "path": str(source_path),
                "char_count": len(canonical_text),
                "byte_count": len(canonical_text.encode("utf-8")),
                "sha256": hashlib.sha256(canonical_text.encode("utf-8")).hexdigest(),
            }
            full_run_ref = f"typed-spacy-run:{uuid4().hex}"
            full_document_ref = f"document:b1-full:{uuid4().hex}"
            full_carrier = run_streaming_spacy_execution(
                database_url=isolated_url,
                run_ref=full_run_ref,
                document_ref=full_document_ref,
                canonical_text=canonical_text,
                parser_contract_ref="parser:spacy:b1-authority-full:v1",
                artifact_root=output_root / "full-parser-artifacts",
                worker_count=2,
                policy=ParserStreamingPolicy(
                    target_chars=32_768,
                    context_chars=2_048,
                    batch_size=4,
                    cache_docbin=True,
                ),
            )
            receipt["full_run_ref"] = full_run_ref
            receipt["full_document_ref"] = full_document_ref
            receipt["full_carrier"] = dict(full_carrier["parser_receipt"])
            receipt["full_hierarchy_diagnostic"] = diagnose_authored_hierarchy(
                isolated_url,
                run_ref=full_run_ref,
                document_ref=full_document_ref,
            )
            receipt["b1_benchmark"] = benchmark_sentence_paragraph_delta_transport(
                isolated_url,
                run_ref=full_run_ref,
                document_ref=full_document_ref,
                limit_sentences=100_000,
            )
            benchmark = receipt["b1_benchmark"]
            receipt["full_b1_passed"] = bool(
                benchmark["paragraph_membership_complete"]
                and benchmark["transport_fusion_equal_direct_union"]
                and benchmark["interface_projection_equal_direct_union"]
                and benchmark["work"]["zero_source_token_rescan"]
            )
        receipt["state"] = "passed" if (
            receipt["smoke_passed"] and receipt.get("full_b1_passed", True)
        ) else "failed"
    except Exception as error:
        receipt["state"] = "failed"
        receipt["error_type"] = type(error).__name__
        receipt["error"] = str(error)
    rendered = json.dumps(receipt, indent=2, sort_keys=True, default=str) + "\n"
    receipt_path = output_root / "b1-authority-certification-receipt.json"
    receipt_path.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if receipt["state"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
