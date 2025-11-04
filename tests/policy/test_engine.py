import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import yaml

from src.policy.engine import CulturalFlags, PolicyEngine, resolve_cultural_flag
from src.graph import GraphNode, NodeType

RULES = ROOT / "data" / "cultural_rules.yaml"


def test_omit_without_override():
    engine = PolicyEngine.from_yaml(str(RULES))
    node = GraphNode(
        type=NodeType.DOCUMENT,
        identifier="n1",
        metadata={"secret": "x"},
        cultural_flags=[CulturalFlags.SACRED_DATA.value],
    )
    assert engine.enforce(node) is None


def test_transform_hook():
    transformed = []
    policy = {
        "rules": [
            {"flag": CulturalFlags.PUBLIC_DOMAIN.name, "action": "transform"}
        ],
        "default": "allow",
    }
    engine = PolicyEngine(policy, inference_hook=lambda f, a: transformed.append((f, a)))
    action = engine.evaluate({CulturalFlags.PUBLIC_DOMAIN})
    assert action == "transform"
    assert transformed == [(CulturalFlags.PUBLIC_DOMAIN, "transform")]


def test_default_allow():
    policy = {
        "rules": [{"flag": CulturalFlags.SACRED_DATA.name, "action": "deny"}],
        "default": "allow",
    }
    engine = PolicyEngine(policy)
    action = engine.evaluate({CulturalFlags.PUBLIC_DOMAIN})
    assert action == "allow"


def test_nested_policy_require():
    policy = {
        "if": CulturalFlags.SACRED_DATA.name,
        "then": {
            "if": CulturalFlags.PUBLIC_DOMAIN.name,
            "then": "allow",
            "else": "require",
        },
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
        cultural_flags=[CulturalFlags.PERSONALLY_IDENTIFIABLE_INFORMATION.value],
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
        cultural_flags=[CulturalFlags.PERSONALLY_IDENTIFIABLE_INFORMATION.value],
    )
    allowed = engine.enforce(node, consent=True, phase="export")
    assert allowed.metadata["pii"] == "x"


def test_enum_matches_registry():
    with open(ROOT / "data" / "cultural_flags.yaml", "r", encoding="utf-8") as fh:
        registry = yaml.safe_load(fh) or {}
    assert {flag.value for flag in CulturalFlags} == set(registry.keys())


def test_resolve_aliases():
    alias = resolve_cultural_flag("pii")
    assert alias is CulturalFlags.PERSONALLY_IDENTIFIABLE_INFORMATION
