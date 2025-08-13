import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.policy.engine import CulturalFlags, PolicyEngine
from src.graph import GraphNode, NodeType

policy_json = json.dumps(
    {
        "name": "SacredDataGuard",
        "rules": [
            {"flag": "SACRED_DATA", "action": "deny"},
            {"flag": "PERSONALLY_IDENTIFIABLE_INFORMATION", "action": "log"},
        ],
        "default": "allow",
    }
)


def test_deny_and_log():
    logs = []
    engine = PolicyEngine.from_json(
        policy_json, storage_hook=lambda f, a: logs.append((f, a))
    )
    action = engine.evaluate({CulturalFlags.SACRED_DATA})
    assert action == "deny"
    assert logs == [(CulturalFlags.SACRED_DATA, "deny")]


def test_log_action():
    logs = []
    engine = PolicyEngine.from_json(
        policy_json, storage_hook=lambda f, a: logs.append((f, a))
    )
    action = engine.evaluate({CulturalFlags.PERSONALLY_IDENTIFIABLE_INFORMATION})
    assert action == "log"
    assert logs == [
        (CulturalFlags.PERSONALLY_IDENTIFIABLE_INFORMATION, "log")
    ]


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


def test_enforce_redacts_without_consent():
    engine = PolicyEngine({})
    node = GraphNode(
        type=NodeType.DOCUMENT,
        identifier="n1",
        metadata={"secret": "x"},
        consent_required=True,
    )
    redacted = engine.enforce(node, consent=False)
    assert redacted.metadata == {}


def test_enforce_allows_with_consent():
    engine = PolicyEngine({})
    node = GraphNode(
        type=NodeType.DOCUMENT,
        identifier="n1",
        metadata={"secret": "x"},
        consent_required=True,
    )
    allowed = engine.enforce(node, consent=True)
    assert allowed.metadata == {"secret": "x"}
