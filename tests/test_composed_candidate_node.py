from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from src.models.composed_candidate_node import (
    build_composed_candidate_node_dict,
    load_composed_candidate_node_schema,
    validate_composed_candidate_node_dict,
)


def _load_payload() -> dict:
    path = Path(__file__).resolve().parents[1] / "examples" / "composed_candidate_node_minimal.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_composed_candidate_node_example_validates() -> None:
    payload = _load_payload()
    schema = load_composed_candidate_node_schema()
    jsonschema.validate(payload, schema)
    validate_composed_candidate_node_dict(payload)


def test_composed_candidate_node_builder_normalizes_canonical_fields() -> None:
    payload = build_composed_candidate_node_dict(
        kind=" composed_candidate_node ",
        predicate_family=" legal_procedural ",
        slots={
            "subject": " actor:john_roberts ",
            "predicate": " confirmed_by ",
            "object": " actor:u_s_senate ",
        },
        content_refs=[{"kind": " source_unit ", "value": " source://demo/transcript/1 ", "note": "kept"}],
        authority_wrapper={"kind": " authority_wrapper ", "value": " judicial_review_gate "},
        status=" candidate ",
        support_phi_ids=[" phi:demo:001 "],
        span_refs=[{"kind": " source_span ", "value": " span://demo/1 ", "start_char": 0, "end_char": 42}],
        provenance_receipts=[{"kind": " source ", "value": " demo_transcript "}],
        section=" Judicial review ",
        genre=" legal_ir ",
    )

    assert payload["kind"] == "composed_candidate_node"
    assert payload["predicate_family"] == "legal_procedural"
    assert payload["slots"]["subject"] == " actor:john_roberts "
    assert payload["content_refs"][0]["kind"] == "source_unit"
    assert payload["content_refs"][0]["value"] == "source://demo/transcript/1"
    assert payload["authority_wrapper"]["value"] == "judicial_review_gate"
    assert payload["status"] == "candidate"
    assert payload["support_phi_ids"] == ["phi:demo:001"]
    assert payload["section"] == "Judicial review"
    assert payload["genre"] == "legal_ir"
    jsonschema.validate(payload, load_composed_candidate_node_schema())


def test_composed_candidate_node_rejects_missing_required_fields() -> None:
    payload = _load_payload()
    del payload["support_phi_ids"]

    with pytest.raises(jsonschema.ValidationError):
        validate_composed_candidate_node_dict(payload)
