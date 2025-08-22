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


def test_transform_hook():
    transformed = []
    policy = {
        "rules": [{"flag": "PUBLIC_DOMAIN", "action": "transform"}],
        "default": "allow",
    }
    engine = PolicyEngine(policy, inference_hook=lambda f, a: transformed.append((f, a)))
    action = engine.evaluate({CulturalFlags.PUBLIC_DOMAIN})
    assert action == "transform"
    assert transformed == [(CulturalFlags.PUBLIC_DOMAIN, "transform")]


def test_default_allow():
    policy = {
        "rules": [{"flag": "SACRED_DATA", "action": "deny"}],
        "default": "allow",
    }
    engine = PolicyEngine(policy)
    action = engine.evaluate({CulturalFlags.PUBLIC_DOMAIN})
    assert action == "allow"


def test_nested_policy_require():
    policy = {
        "if": "SACRED_DATA",
        "then": {"if": "PUBLIC_DOMAIN", "then": "allow", "else": "require"},
        "else": "allow",
    }
    engine = PolicyEngine(policy)
    action = engine.evaluate({CulturalFlags.SACRED_DATA})
    assert action == "require"


def test_enforce_redacts_without_consent():
    engine = PolicyEngine({})

def test_redact_without_consent():
    engine = PolicyEngine.from_yaml(str(RULES))
    node = GraphNode(
        type=NodeType.DOCUMENT,
        identifier="n2",
        metadata={"pii": "x"},
        cultural_flags=["PERSONALLY_IDENTIFIABLE_INFORMATION"],
    )
    redacted = engine.enforce(node, consent=False)
    assert redacted.metadata == {"summary": "Content withheld due to policy"}

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
