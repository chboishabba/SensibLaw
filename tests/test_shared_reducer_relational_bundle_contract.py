from __future__ import annotations

from sensiblaw.interfaces import build_canonical_conversation_text
from sensiblaw.interfaces.shared_reducer import collect_canonical_relational_bundle


_ALLOWED_RELATION_TYPES = {
    "predicate",
    "modifier",
    "conjunction",
    "temporal",
    "composition",
}


def _validate_relational_bundle_v1(bundle: dict) -> None:
    assert bundle["version"] == "relational_bundle_v1"
    assert isinstance(bundle["atoms"], list)
    assert isinstance(bundle["relations"], list)

    atom_by_id = {}
    for atom in bundle["atoms"]:
        assert isinstance(atom["id"], str)
        assert atom["id"] not in atom_by_id
        assert isinstance(atom["text"], str)
        assert isinstance(atom["span"], list)
        assert len(atom["span"]) == 2
        assert atom["span"][0] < atom["span"][1]
        atom_by_id[atom["id"]] = atom

    relation_ids: set[str] = set()
    for relation in bundle["relations"]:
        assert isinstance(relation["id"], str)
        assert relation["id"] not in relation_ids
        relation_ids.add(relation["id"])
        assert relation["type"] in _ALLOWED_RELATION_TYPES
        assert relation["roles"]
        for role in relation["roles"]:
            assert isinstance(role["role"], str)
            has_atom = "atom" in role
            has_value = "value" in role
            assert has_atom or has_value
            if has_atom:
                assert role["atom"] in atom_by_id
            if relation["type"] == "composition" and role["role"] == "mode":
                assert role["value"] == "question"
                assert role["span_start"] < role["span_end"]
                assert bundle["canonical_text"][role["span_start"]:role["span_end"]]


def test_relational_bundle_contract_matches_hedging_volatility_shape() -> None:
    canonical_text = build_canonical_conversation_text(
        text="how does crypto promise to hedge asset volatility and uncertainty in 2026",
        speaker="synthetic-community-user-008",
    )

    bundle = collect_canonical_relational_bundle(canonical_text)
    atom_text_by_id = {atom["id"]: atom["text"] for atom in bundle["atoms"]}
    _validate_relational_bundle_v1(bundle)

    assert bundle["version"] == "relational_bundle_v1"
    assert bundle["canonical_text"] == canonical_text

    predicate_pairs = [
        tuple(atom_text_by_id[role["atom"]] for role in relation["roles"])
        for relation in bundle["relations"]
        if relation["type"] == "predicate"
    ]
    assert ("hedge", "volatility") in predicate_pairs

    modifier_pairs = [
        tuple(atom_text_by_id[role["atom"]] for role in relation["roles"])
        for relation in bundle["relations"]
        if relation["type"] == "modifier"
    ]
    assert ("volatility", "uncertainty") in modifier_pairs

    conjunction_sets = [
        {atom_text_by_id[role["atom"]] for role in relation["roles"]}
        for relation in bundle["relations"]
        if relation["type"] == "conjunction"
    ]
    assert {"volatility", "uncertainty"} in conjunction_sets

    temporal_anchors = [
        atom_text_by_id[relation["roles"][0]["atom"]]
        for relation in bundle["relations"]
        if relation["type"] == "temporal"
    ]
    assert "2026" in temporal_anchors

    composition_values = [
        relation["roles"][0]["value"]
        for relation in bundle["relations"]
        if relation["type"] == "composition"
    ]
    assert "question" in composition_values
