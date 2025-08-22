import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.frame.compile import compile_frame


def test_compile_deterministic_and_receipts():
    node = {"id": "n1", "label": "Alpha"}
    neighbors = [
        {"id": "n2", "receipts": ["r-001"]},
        {"id": "n3", "receipts": ["r-002"]},
    ]
    factors = [{"id": "f1", "receipts": ["r-003"]}]

    first = compile_frame(node, neighbors, factors)
    second = compile_frame(node, neighbors, factors)

    assert len(first["thesis"].split()) <= 12
    assert any(r in first["summary"] for r in ["r-001", "r-002", "r-003"])
    assert any(r in first["brief"] for r in ["r-001", "r-002", "r-003"])
    assert first == second


def test_compile_no_neighbors():
    node = {"id": "n1", "label": "Alpha"}
    result = compile_frame(node, [], [])
    assert "no neighbors" in result["thesis"].lower()
