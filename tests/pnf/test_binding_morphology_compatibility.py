from __future__ import annotations

from src.pnf.binding_candidate_sets import compact_binding_artifacts


def _factor(
    factor_ref: str,
    factor_type: str,
    span_ref: str,
    *,
    reference: bool = False,
) -> dict[str, object]:
    alternatives: list[dict[str, object]] = []
    residuals: list[str] = []
    if reference:
        alternatives.append(
            {
                "alternative_ref": f"{factor_ref}:entity-reference",
                "type_ref": "semantic.reference_candidate",
                "value": {"referential_type": "entity_reference"},
                "derivation_refs": ["parser:test"],
            }
        )
        residuals = ["antecedent_unresolved", "referential_type_unresolved"]
    return {
        "factor_ref": factor_ref,
        "factor_type": factor_type,
        "alternatives": alternatives,
        "constraints": [],
        "residuals": residuals,
        "closure_state": (
            "requires_external_resolution" if reference else "locally_closed"
        ),
        "metadata": {"atom_span_ref": span_ref},
    }


def _artifacts(candidate_number: str | None) -> dict[str, object]:
    reference = _factor(
        "factor:she",
        "semantic.argument.subject",
        "semantic:she",
        reference=True,
    )
    candidate = _factor(
        "factor:engineers",
        "semantic.mention_identity",
        "semantic:engineers",
    )
    candidate_morphology = (
        {"Number": [candidate_number]} if candidate_number is not None else {}
    )
    return {
        "canonical_text": "Engineers arrived. She spoke.",
        "licensing": {"mentions": []},
        "semantic_annotation_layer": {
            "token_annotations": [
                {
                    "token_index": 0,
                    "annotation_type": "parser.pos",
                    "value": "NOUN",
                    "provenance_refs": ["parser:test"],
                },
                {
                    "token_index": 0,
                    "annotation_type": "parser.morphology",
                    "value": candidate_morphology,
                    "provenance_refs": ["parser:test"],
                },
                {
                    "token_index": 0,
                    "annotation_type": "parser.sentence",
                    "value": 0,
                    "provenance_refs": ["parser:test"],
                },
                {
                    "token_index": 3,
                    "annotation_type": "parser.pos",
                    "value": "PRON",
                    "provenance_refs": ["parser:test"],
                },
                {
                    "token_index": 3,
                    "annotation_type": "parser.morphology",
                    "value": {"Number": ["Sing"], "Person": ["3"]},
                    "provenance_refs": ["parser:test"],
                },
                {
                    "token_index": 3,
                    "annotation_type": "parser.sentence",
                    "value": 1,
                    "provenance_refs": ["parser:test"],
                },
            ],
            "span_annotations": [
                {
                    "span_ref": "parser:engineers",
                    "start_token": 0,
                    "end_token": 1,
                    "annotation_type": "parser_token",
                    "value": {"start_char": 0, "end_char": 9},
                    "provenance_refs": ["parser:test"],
                },
                {
                    "span_ref": "semantic:engineers",
                    "start_token": 0,
                    "end_token": 1,
                    "annotation_type": "semantic_atom",
                    "value": {"text": "Engineers"},
                    "provenance_refs": ["parser:test"],
                },
                {
                    "span_ref": "parser:she",
                    "start_token": 3,
                    "end_token": 4,
                    "annotation_type": "parser_token",
                    "value": {"start_char": 19, "end_char": 22},
                    "provenance_refs": ["parser:test"],
                },
                {
                    "span_ref": "semantic:she",
                    "start_token": 3,
                    "end_token": 4,
                    "annotation_type": "semantic_atom",
                    "value": {"text": "She"},
                    "provenance_refs": ["parser:test"],
                },
            ],
            "relation_annotations": [],
        },
        "pnf_graph": {
            "graph_ref": "pnf:morphology-test",
            "document_ref": "document:morphology-test",
            "factors": [candidate, reference],
            "constraints": [],
            "relation_refs": [],
        },
        "refined_pnf_graph": {
            "graph_ref": "pnf:morphology-test",
            "document_ref": "document:morphology-test",
            "factors": [candidate, reference],
            "constraints": [],
            "relation_refs": [],
        },
        "local_evidence": [],
        "typed_meets": [],
        "factor_refinements": [],
        "resolution_demands": [],
    }


def test_evidenced_number_mismatch_is_excluded_with_reason() -> None:
    artifacts = compact_binding_artifacts(_artifacts("Plur"))
    candidate_set = artifacts["binding_candidate_sets"][0]

    assert candidate_set["referential_type_ref"] == "entity_reference"
    assert candidate_set["member_count"] == 0
    assert candidate_set["exclusion_summaries"] == [
        {
            "reason_ref": "incompatible_morphology:Number",
            "excluded_count": 1,
            "generator_build_ref": candidate_set["generator_build_ref"],
        }
    ]


def test_missing_candidate_number_retains_candidate_without_fabrication() -> None:
    artifacts = compact_binding_artifacts(_artifacts(None))
    candidate_set = artifacts["binding_candidate_sets"][0]

    assert candidate_set["member_count"] == 1
    assert candidate_set["members"][0]["candidate_factor_ref"] == (
        "factor:engineers"
    )
    assert candidate_set["exclusion_summaries"] == []
