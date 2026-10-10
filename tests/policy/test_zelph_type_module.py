from __future__ import annotations

import pytest

from src.policy.external_graph_bridge import build_graph_view
from src.policy.pruned_graph_preservation import build_query_family_preservation_receipt
from src.policy.zelph_type_module import build_zelph_type_module, type_absence_is_admissible


def _graph() -> dict[str, object]:
    return build_graph_view(
        graph_view_id="graph:type-q1",
        artifact_id="zelph:wikidata-pruned",
        artifact_revision="2026-03-09-pruned",
        coverage_state="complete",
        selected_sections=["left", "right"],
        selected_chunks=[{"which": "left", "chunkIndex": 1, "sizeBytes": 10}],
        selected_bytes=10,
        coverage_policy={"query_family": "query:p31-p279-type-closure"},
        completeness_receipt_ref="coverage:graph:type-q1",
    )


def _preservation(state: str) -> dict[str, object]:
    kwargs = {
        "source_artifact_ref": "wikidata:full",
        "source_revision_ref": "2026-03-09",
        "pruned_artifact_ref": "zelph:wikidata-pruned",
        "pruned_revision_ref": "2026-03-09-pruned",
        "query_family_ref": "query:p31-p279-type-closure",
        "preservation_state": state,
        "soundness_receipt_ref": "proof:type-sound",
        "covered_relations": ["P31", "P279"],
    }
    if state == "sound_and_complete":
        kwargs["completeness_receipt_ref"] = "proof:type-complete"
    return build_query_family_preservation_receipt(**kwargs)


def test_sound_only_module_accepts_positive_type_relations_but_not_absence() -> None:
    module = build_zelph_type_module(
        subject_qid="Q1",
        graph_view=_graph(),
        relation_observations=[
            {"property_id": "P31", "object_ref": "Q783794"},
            {"source_ref": "Q783794", "property_id": "P279", "object_ref": "Q4830453"},
        ],
        preservation_receipt=_preservation("sound_only"),
        module_receipt_ref="module:q1:type",
    )
    assert module["positive_answers_sound"] is True
    assert module["negative_answers_complete"] is False
    assert type_absence_is_admissible(module) is False
    assert module["native_statement_authority"] is False


def test_complete_family_receipt_can_admit_negative_type_answer() -> None:
    module = build_zelph_type_module(
        subject_qid="Q1",
        graph_view=_graph(),
        relation_observations=[],
        preservation_receipt=_preservation("sound_and_complete"),
        module_receipt_ref="module:q1:type",
    )
    assert type_absence_is_admissible(module) is True


def test_non_type_relation_is_rejected_from_type_module() -> None:
    with pytest.raises(ValueError, match="P31 or P279"):
        build_zelph_type_module(
            subject_qid="Q1",
            graph_view=_graph(),
            relation_observations=[{"property_id": "P5991", "object_ref": "QX"}],
            preservation_receipt=_preservation("sound_only"),
            module_receipt_ref="module:q1:type",
        )
