"""Install portable numeric semantic receipts on strict production execution.

This wraps the already-authoritative numeric compile/persist functions. It does
not introduce a second compiler or publication path. Fresh compilation derives
its portable receipt from the closed numeric authority exactly once; persistence
consumes that process-local receipt and stores it beside the existing completed
build. Cached reuse skips compilation and loads the durable build receipt.
"""

from __future__ import annotations

from contextvars import ContextVar
from functools import wraps
import json
import os
from pathlib import Path
from typing import Any

from src.storage.postgres.numeric_semantic_receipt import (
    NumericSemanticReceipt,
    compute_numeric_semantic_receipt,
    load_numeric_semantic_receipt,
    persist_numeric_semantic_receipt,
)
from src.storage.postgres.operational_build_store import operational_build_ref
from src.storage.postgres.spacy_parser_model import connect


_INSTALL_MARKER = "_numeric_semantic_receipt_execution_installed"
_FRESH_RECEIPT: ContextVar[
    tuple[tuple[str, str, str, str], NumericSemanticReceipt] | None
] = ContextVar("sensiblaw_fresh_numeric_semantic_receipt", default=None)


def _receipt_key(
    *, document_ref: str, canonical_text_sha256: str, parser_contract_ref: str,
    build_key_sha256: str,
) -> tuple[str, str, str, str]:
    return (
        document_ref,
        canonical_text_sha256,
        parser_contract_ref,
        build_key_sha256,
    )


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


def _emit_acceptance_coordinate(receipt: NumericSemanticReceipt) -> None:
    """Write one small audit-boundary receipt when an acceptance run asks."""

    raw = os.environ.get("SENSIBLAW_NUMERIC_SEMANTIC_RECEIPT_PATH")
    if not raw:
        return
    path = Path(raw)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = receipt.to_mapping()
    payload["transport_authority"] = "audit_boundary_only"
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
        key = _receipt_key(
            document_ref=str(kwargs["document_ref"]),
            canonical_text_sha256=str(kwargs["canonical_text_sha256"]),
            parser_contract_ref=str(kwargs["parser_contract_ref"]),
            build_key_sha256=str(kwargs["build_key_sha256"]),
        )
        _FRESH_RECEIPT.set((key, receipt))
        compilation.artifacts["numeric_semantic_receipt"] = receipt.to_mapping()
        authority = compilation.artifacts.get("numeric_pnf_authority")
        if isinstance(authority, dict):
            authority["semantic_receipt_ref"] = receipt.receipt_ref
            authority["semantic_receipt_sha256"] = receipt.receipt_sha256.hex()
        return compilation

    @wraps(original_persist)
    def persist_wrapper(*args: Any, **kwargs: Any):
        # The original persist either reuses an existing build without compiling,
        # or calls the wrapped compile above.  Capture the fresh receipt only
        # after that decision has been made.
        demand_refs = original_persist(*args, **kwargs)
        document_ref = str(kwargs["entry"]["document_ref"])
        parser_contract_ref = str(kwargs["context"].annotation_backend_ref)
        key = _receipt_key(
            document_ref=document_ref,
            canonical_text_sha256=str(kwargs["canonical_text_sha256"]),
            parser_contract_ref=parser_contract_ref,
            build_key_sha256=str(kwargs["build_key_sha256"]),
        )
        fresh = _FRESH_RECEIPT.get()
        receipt = fresh[1] if fresh is not None and fresh[0] == key else None
        if fresh is not None and fresh[0] == key:
            _FRESH_RECEIPT.set(None)

        build_ref = operational_build_ref(
            document_ref=document_ref,
            compiler_contract_ref=numeric.NUMERIC_PNF_COMPILER_CONTRACT,
            build_key_sha256=str(kwargs["build_key_sha256"]),
        )
        connection = connect(str(kwargs["database_url"]))
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    durable = load_numeric_semantic_receipt(cursor, build_ref=build_ref)
                    if durable is not None:
                        # Cached replay: the durable receipt is the authority.
                        # Fresh compilation: equality is a fail-closed consistency
                        # check between pre-publication calculation and stored build.
                        if (
                            receipt is not None
                            and durable.receipt_sha256 != receipt.receipt_sha256
                        ):
                            raise RuntimeError(
                                "fresh numeric receipt disagrees with completed build receipt"
                            )
                        receipt = durable
                    elif receipt is not None:
                        persist_numeric_semantic_receipt(
                            cursor, build_ref=build_ref, receipt=receipt
                        )
                    else:
                        # Compatibility with builds created before migration 140:
                        # compute once, persist, and from then on replay is O(1)
                        # in semantic receipt construction.
                        receipt = compute_numeric_semantic_receipt(
                            cursor,
                            run_ref=str(kwargs["run_ref"]),
                            document_ref=document_ref,
                            canonical_text_sha256=str(kwargs["canonical_text_sha256"]),
                            parser_contract_ref=parser_contract_ref,
                            compiler_contract_ref=numeric.NUMERIC_PNF_COMPILER_CONTRACT,
                        )
                        persist_numeric_semantic_receipt(
                            cursor, build_ref=build_ref, receipt=receipt
                        )
        finally:
            connection.close()
        assert receipt is not None
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
