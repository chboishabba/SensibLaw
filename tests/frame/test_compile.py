"""Fail-closed frame compiler contracts."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.frame.compile import compile_frame


def test_compile_deterministic_with_all_required_evidence():
    node = {"id": "n1", "thesis": "Alpha is supported", "action": "Review Alpha"}
    neighbors = [{"id": "n2", "receipts": ["r-001", "r-002"]}]
    factors = [{"id": "f1", "receipts": ["r-003"]}]
    result = compile_frame(node, neighbors, factors)
    assert result == compile_frame(node, neighbors, factors)
    assert result == {
        "thesis": "Alpha is supported",
        "summary": "Receipts referenced: r-001, r-002, r-003",
        "brief": "Receipts: r-001, r-002, r-003",
        "action": "Review Alpha",
    }


@pytest.mark.parametrize("field,value", [
    ("thesis", None), ("thesis", "  "), ("thesis", 3),
    ("action", None), ("action", "\n "), ("action", []),
])
def test_missing_thesis_or_action_fails(field, value):
    node = {"thesis": "claim", "action": "review"}
    node[field] = value
    with pytest.raises(ValueError, match=f"missing {field}"):
        compile_frame(node, [{"receipts": ["r-1"]}], [])


@pytest.mark.parametrize("neighbors,factors", [
    ([], []), ([{}], []), ([{"receipts": []}], []),
    ([{"receipts": [" "]}], []), ([{"receipts": [None]}], []),
    ([{"receipts": "r-1"}], []), ([{"receipts": 123}], []),
])
def test_missing_or_invalid_receipt_fails(neighbors, factors):
    with pytest.raises(ValueError, match="receipt"):
        compile_frame({"thesis": "claim", "action": "review"}, neighbors, factors)


def test_factor_receipt_suffices_without_neighbors():
    result = compile_frame({"thesis": "claim", "action": "review"}, [], [{"receipts": ["r-1"]}])
    assert result["brief"] == "Receipts: r-1"


def test_no_fabricated_thesis_from_label():
    with pytest.raises(ValueError, match="missing thesis"):
        compile_frame({"label": "Alpha", "action": "review"}, [{"receipts": ["r-1"]}], [])
