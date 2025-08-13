import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.graph.models import NodeType, EdgeType


def test_extended_enums():
    assert NodeType.CASE.value == "case"
    assert NodeType.CONCEPT.value == "concept"
    assert EdgeType.FOLLOWS.value == "follows"
    assert EdgeType.DISTINGUISHES.value == "distinguishes"
