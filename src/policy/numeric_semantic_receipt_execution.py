"""Install portable numeric semantic receipts on strict production execution.

This wraps the already-authoritative numeric compile/persist functions.  It does
not introduce a second compiler or publication path.  Fresh compilation derives
its portable receipt from the closed numeric authority; persistence stores that
receipt beside the existing completed build.  Cached reuse loads the same build
receipt, so replay parity no longer depends on compatibility manifests.
"""

from __future__ import annotations

from functools import wraps
import json
import os
from pathlib import Path
from typing import Any

from src.storage.postgres.numeric_semantic_receipt import (
    compute_numeric_semantic_receipt,
    load_numeric_semantic_receipt,
    persist_numeric_semantic_receipt,
)
from src.storage.postgres.operational_build_store import operational_build_ref
from src.storage.postgres.spacy_parser_model import connect


_INSTALL_MARKER = "_numeric_semantic_receipt_execution_installed"


def _compute(
    *,
    database_url: str,
    run_ref: str,
    document_ref: str,
    canonical_text_sha256: str,
    parser_contract_ref: str,
    compiler_contract_ref: str,
):
    connection = connect(database_url)
    try:
        with connection.cursor() as cursor:
            return compute_numeric_semantic_receipt(
                cursor,
                run_ref=run_ref,
                document_ref=document_ref,
                canonical_text_sha256=canonical_text_sha256,
                parser_contract_ref=parser_contract_ref,
                compiler_contract_ref=compiler_contract_ref,
            )
    finally:
        connection.close()


def _emit_acceptance_coordinate(receipt: Any) -> None:
    """Write one tiny audit-boundary coordinate when an acceptance run asks.

    This is deliberately not a semantic working representation.  The database
    receipt remains authority; this file exists only so disposable PostgreSQL
    runs can transport the portable digest after teardown.
    """

    raw = os.environ.get("SENSIBLAW_NUMERIC_SEMANTIC_RECEIPT_PATH")
    if not raw:
        return
    path = Path(raw)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "sensiblaw.numeric-semantic-parity-coordinate.v1",
        "receipt_ref": receipt.receipt_ref,
        "receipt_sha256": receipt.receipt_sha256.hex(),
        "identity_basis": "portable_numeric_semantic_publication_receipt:v1",
    }
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def install_numeric_semantic_receipt_execution() -> bool:
    from src.policy import numeric_pnf_compilation as numeric
    from src.policy import streaming_spacy_parser_execution as streaming

    if getattr(numeric, _INSTALL_MARKER, False):
        return False

    original_compile = numeric.compile_numeric_pnf_document
    original_persist = numeric.persist_numeric_pnf_document

    @wraps(original_compile)
    def compile_wrapper(*args: Any, **kwargs: Any):
        compilation = original_compile(*args, **kwargs)
        receipt = _compute(
            database_url=str(kwargs["database_url"]),
            run_ref=str(kwargs["run_ref"]),
            document_ref=str(kwargs["document_ref"]),
            canonical_text_sha256=str(kwargs["canonical_text_sha256"]),
            parser_contract_ref=str(kwargs["parser_contract_ref"]),
            compiler_contract_ref=numeric.NUMERIC_PNF_COMPILER_CONTRACT,
        )
        compilation.artifacts["numeric_semantic_receipt"] = receipt.to_mapping()
        authority = compilation.artifacts.get("numeric_pnf_authority")
        if isinstance(authority, dict):
            authority["semantic_receipt_ref"] = receipt.receipt_ref
            authority["semantic_receipt_sha256"] = receipt.receipt_sha256.hex()
        return compilation

    @wraps(original_persist)
    def persist_wrapper(*args: Any, **kwargs: Any):
        demand_refs = original_persist(*args, **kwargs)
        document_ref = str(kwargs["entry"]["document_ref"])
        build_ref = operational_build_ref(
            document_ref=document_ref,
            compiler_contract_ref=numeric.NUMERIC_PNF_COMPILER_CONTRACT,
            build_key_sha256=str(kwargs["build_key_sha256"]),
        )
        connection = connect(str(kwargs["database_url"]))
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    receipt = load_numeric_semantic_receipt(cursor, build_ref=build_ref)
                    if receipt is None:
                        receipt = compute_numeric_semantic_receipt(
                            cursor,
                            run_ref=str(kwargs["run_ref"]),
                            document_ref=document_ref,
                            canonical_text_sha256=str(kwargs["canonical_text_sha256"]),
                            parser_contract_ref=str(kwargs["context"].annotation_backend_ref),
                            compiler_contract_ref=numeric.NUMERIC_PNF_COMPILER_CONTRACT,
                        )
                        persist_numeric_semantic_receipt(
                            cursor,
                            build_ref=build_ref,
                            receipt=receipt,
                        )
        finally:
            connection.close()
        _emit_acceptance_coordinate(receipt)
        return demand_refs

    numeric.compile_numeric_pnf_document = compile_wrapper
    numeric.persist_numeric_pnf_document = persist_wrapper
    # streaming_spacy_parser_execution imported these names directly. Rebind
    # its module globals so the already-installed production wrappers use the
    # receipt-bearing functions without reconstructing their signatures.
    streaming.compile_numeric_pnf_document = compile_wrapper
    streaming.persist_numeric_pnf_document = persist_wrapper
    setattr(numeric, _INSTALL_MARKER, True)
    return True


__all__ = ["install_numeric_semantic_receipt_execution"]
