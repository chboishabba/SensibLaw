from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.policy.engine import PolicyEngine
from src.graph import GraphNode, NodeType

RULES = ROOT / "data" / "cultural_rules.yaml"


def test_omit_without_override():
    engine = PolicyEngine.from_yaml(str(RULES))
    node = GraphNode(
        type=NodeType.DOCUMENT,
        identifier="n1",
        metadata={"secret": "x"},
        cultural_flags=["SACRED_DATA"],
    )
    assert engine.enforce(node) is None


def test_redact_without_consent():
    engine = PolicyEngine.from_yaml(str(RULES))
    node = GraphNode(
        type=NodeType.DOCUMENT,
        identifier="n2",
        metadata={"pii": "x"},
        cultural_flags=["PERSONALLY_IDENTIFIABLE_INFORMATION"],
    )
    redacted = engine.enforce(node)
    assert redacted.metadata["pii"] != "x"


def test_override_allows_original():
    engine = PolicyEngine.from_yaml(str(RULES))
    node = GraphNode(
        type=NodeType.DOCUMENT,
        identifier="n3",
        metadata={"pii": "x"},
        cultural_flags=["PERSONALLY_IDENTIFIABLE_INFORMATION"],
    )
    allowed = engine.enforce(node, consent=True, phase="export")
    assert allowed.metadata["pii"] == "x"
