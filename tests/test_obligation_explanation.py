from src.obligations import extract_obligations_from_text
from src.obligation_views import (
    EXPLANATION_SCHEMA_VERSION,
    build_explanations,
    explanations_to_payload,
)


def _normalize_atoms(explanation: dict) -> dict:
    atoms = explanation["atoms"]
    return {
        "actor": atoms["actor"]["normalized"] if atoms.get("actor") else None,
        "action": atoms["action"]["normalized"] if atoms.get("action") else None,
        "object": atoms["object"]["normalized"] if atoms.get("object") else None,
        "conditions": [(c["type"], c.get("content_span")) for c in atoms["conditions"]],
        "scopes": [(s["category"], s["normalized"], s.get("content_span")) for s in atoms["scopes"]],
        "lifecycle": [(l["kind"], l["normalized"], l.get("content_span")) for l in atoms["lifecycle"]],
    }


def test_explanations_survive_clause_numbering_and_spacing_noise():
    plain_text = "The operator must keep records within 7 days."
    numbered_text = "(1)  The operator   must keep records within 7 days."

    base = build_explanations(plain_text, extract_obligations_from_text(plain_text))
    noisy = build_explanations(numbered_text, extract_obligations_from_text(numbered_text))

    assert len(base) == len(noisy) == 1
    assert _normalize_atoms(base[0]) == _normalize_atoms(noisy[0])
    assert base[0]["atoms"]["scopes"][0]["category"] == "time"
    assert base[0]["atoms"]["action"]["content_span"] == noisy[0]["atoms"]["action"]["content_span"]


def test_scope_ordering_is_deterministic():
    text = "The operator must keep records within 7 days during operations on the premises."
    explanations = build_explanations(text, extract_obligations_from_text(text))
    scopes = explanations[0]["atoms"]["scopes"]
    ordered_categories = [s["category"] for s in scopes]
    # sorted by category then normalized phrase
    assert ordered_categories == ["context", "place", "time"]
    assert [s["normalized"] for s in scopes] == ["during operations", "on the premises", "within 7 days"]


def test_explanation_payload_version_and_flag_respect():
    text = "The operator must keep records."
    obligations = extract_obligations_from_text(text, enable_action_binding=False)
    explanations = build_explanations(text, obligations)
    assert explanations[0]["atoms"]["action"] is None
    payload = explanations_to_payload(explanations)
    assert payload["version"] == EXPLANATION_SCHEMA_VERSION
    assert payload["explanations"][0]["clause_id"] == obligations[0].clause_id
