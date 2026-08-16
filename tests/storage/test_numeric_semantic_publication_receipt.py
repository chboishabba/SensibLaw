from __future__ import annotations

from dataclasses import replace

from src.runtime.numeric_semantic_parity import compare_numeric_receipts
from src.storage.postgres.numeric_semantic_receipt import NumericSemanticReceipt


def _receipt(seed: int = 1) -> NumericSemanticReceipt:
    def digest(offset: int) -> bytes:
        return bytes([(seed + offset) % 256]) * 32

    return NumericSemanticReceipt(
        receipt_sha256=digest(0),
        parser_root_sha256=digest(1),
        object_root_sha256=digest(2),
        factor_root_sha256=digest(3),
        residual_root_sha256=digest(4),
        export_root_sha256=digest(5),
        proof_root_sha256=digest(6),
        object_leaf_count=7,
        factor_leaf_count=5,
        residual_leaf_count=3,
        export_leaf_count=2,
        proof_leaf_count=1,
    )


def test_numeric_receipt_mapping_contains_hierarchical_roots_not_runtime_metadata() -> None:
    payload = _receipt().to_mapping()
    assert payload["receipt_ref"].startswith("numeric-semantic-receipt:v1:")
    for key in (
        "parser_root_sha256",
        "object_root_sha256",
        "factor_root_sha256",
        "residual_root_sha256",
        "export_root_sha256",
        "proof_root_sha256",
    ):
        assert len(payload[key]) == 64
    serialized_keys = set(payload)
    assert not {
        "elapsed_ns",
        "worker_pid",
        "backend_pid",
        "lease_epoch",
        "lease_token",
        "cache_hit",
        "run_ref",
        "document_interface_id",
    } & serialized_keys


def test_numeric_semantic_parity_is_exact_top_root_equality() -> None:
    left = _receipt().to_mapping()
    right = _receipt().to_mapping()
    result = compare_numeric_receipts(left, right)
    assert result["semantic_parity"] is True
    assert result["state"] == "equal"

    changed = replace(_receipt(), proof_root_sha256=b"z" * 32, receipt_sha256=b"y" * 32)
    result = compare_numeric_receipts(left, changed.to_mapping())
    assert result["semantic_parity"] is False
    assert result["state"] == "different"


def test_missing_numeric_receipt_is_unknown_not_negative_evidence() -> None:
    result = compare_numeric_receipts(None, _receipt().to_mapping())
    assert result["semantic_parity"] is None
    assert result["state"] == "numeric_receipt_missing"
