from __future__ import annotations

from pathlib import Path
import shutil

from src.pnf.reference_binding import (
    REFERENCE_BINDING_CONTRACT_REF,
    REFERENCE_REDUCTION_DECLARATION_REF,
    build_set_valued_binding_artifacts,
)
from src.policy.corpus_compilation import compile_directory, default_compiler_context


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "corpora"
    / "reference-binding-mini"
)


def _compile_text(tmp_path: Path, text: str) -> dict[str, object]:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "source.txt").write_text(text, encoding="utf-8")
    result = compile_directory(
        source_dir,
        context=default_compiler_context(),
        output_store=tmp_path / "artifacts",
    )
    artifacts = next(
        row["artifacts"]
        for row in result["compilations"]
        if row["status"] == "compiled"
    )
    return build_set_valued_binding_artifacts(artifacts)


def _sets_by_type(artifacts: dict[str, object]) -> dict[str, list[dict[str, object]]]:
    result: dict[str, list[dict[str, object]]] = {}
    for row in artifacts["binding_candidate_sets"]:
        result.setdefault(str(row["referential_type_ref"]), []).append(row)
    return result


def _reference_factors(artifacts: dict[str, object]) -> list[dict[str, object]]:
    return [
        row
        for row in artifacts["refined_pnf_graph"]["factors"]
        if any(
            alternative["type_ref"] == "semantic.reference_candidate"
            for alternative in row["alternatives"]
        )
    ]


def test_reference_binding_mini_exercises_all_generic_reference_classes(tmp_path):
    corpus = tmp_path / "reference-binding-mini"
    shutil.copytree(FIXTURE, corpus)
    result = compile_directory(
        corpus,
        context=default_compiler_context(),
        output_store=tmp_path / "legacy-artifacts",
    )
    compiled = {
        row["artifacts"]["canonical_text"].strip(): build_set_valued_binding_artifacts(
            row["artifacts"]
        )
        for row in result["compilations"]
        if row["status"] == "compiled"
    }

    assert len(compiled) == 5

    entity = compiled["Ada entered the hall. She spoke."]
    entity_sets = _sets_by_type(entity)["entity_reference"]
    assert any(row["member_count"] >= 1 for row in entity_sets)

    object_reference = compiled["Ada greeted Lin. Lin thanked her."]
    object_factors = [
        row
        for row in _reference_factors(object_reference)
        if row["metadata"].get("role") == "object"
    ]
    assert object_factors
    assert any(
        alternative["type_ref"] == "semantic.binding_candidate_set"
        for alternative in object_factors[0]["alternatives"]
    )
    assert any(
        row["factor_ref"] == object_factors[0]["factor_ref"]
        and row["budget"] == "bounded_document_local_evidence"
        for row in object_reference["resolution_demands"]
    )

    eventuality = compiled["The storm intensified overnight. It caused flooding."]
    eventuality_sets = _sets_by_type(eventuality)["eventuality_reference"]
    assert any(row["member_count"] >= 1 for row in eventuality_sets)

    proposition = compiled[
        "The report alleged that the bridge failed. It was disputed."
    ]
    proposition_sets = _sets_by_type(proposition)["proposition_reference"]
    assert any(row["member_count"] >= 1 for row in proposition_sets)

    expletive = compiled["It was raining."]
    expletive_sets = expletive["binding_candidate_sets"]
    assert {row["referential_type_ref"] for row in expletive_sets} == {
        "entity_reference",
        "eventuality_reference",
        "proposition_reference",
    }
    assert all(row["member_count"] == 0 for row in expletive_sets)
    expletive_factor = _reference_factors(expletive)[0]
    assert any(
        alternative["value"].get("referential_type") == "expletive_realisation"
        for alternative in expletive_factor["alternatives"]
        if isinstance(alternative.get("value"), dict)
    )
    assert "antecedent_unresolved" in expletive_factor["residuals"]

    for artifacts in compiled.values():
        assert artifacts["reference_binding_operational_contract"] == (
            REFERENCE_BINDING_CONTRACT_REF
        )
        assert artifacts["binding_compaction_summary"]["generation_mode"] == (
            "direct_observation_graph_index"
        )
        assert not any(
            row["evidence_type"] == "typed_binding_candidate"
            for row in artifacts["local_evidence"]
        )
        assert all(
            alternative["type_ref"] != "semantic.binding_candidate"
            for factor in artifacts["refined_pnf_graph"]["factors"]
            for alternative in factor["alternatives"]
        )
        assert artifacts["reference_argument_projection_summary"][
            "english_pronoun_catalogue_used"
        ] is False


def test_structural_accessibility_is_not_a_fixed_two_sentence_window(tmp_path):
    artifacts = _compile_text(
        tmp_path,
        "Nova arrived. The doors opened. Music played. She spoke.",
    )
    entity_sets = _sets_by_type(artifacts)["entity_reference"]
    assert any(row["member_count"] >= 1 for row in entity_sets)
    assert any(
        member["accessibility_path_ref"]
        in {
            "accessibility:preceding_discourse_unit",
            "accessibility:preceding_document_unit",
        }
        for row in entity_sets
        for member in row["members"]
    )


def test_morphology_mismatch_is_an_assessment_not_a_missing_candidate(tmp_path):
    artifacts = _compile_text(tmp_path, "Engineers arrived. She spoke.")
    entity_sets = _sets_by_type(artifacts)["entity_reference"]
    assert entity_sets
    assert any(
        summary["reason_ref"].startswith("incompatible_morphology:Number")
        for row in entity_sets
        for summary in row["exclusion_summaries"]
    )
    assert "antecedent_unresolved" in _reference_factors(artifacts)[0]["residuals"]


def test_reference_projection_is_parser_owned_and_idempotent(tmp_path):
    artifacts = _compile_text(tmp_path, "Ada entered. She spoke.")
    declaration_refs = {
        row["declaration_ref"] for row in artifacts["compiler_declarations"]
    }
    assert REFERENCE_REDUCTION_DECLARATION_REF in declaration_refs
    assert artifacts["reference_argument_projection_summary"][
        "english_pronoun_catalogue_used"
    ] is False
    assert build_set_valued_binding_artifacts(artifacts) == artifacts


def test_candidate_set_refinement_retains_uncertainty_and_uses_deltas(tmp_path):
    artifacts = _compile_text(tmp_path, "Ada entered. She spoke.")
    binding_refinements = [
        row
        for row in artifacts["factor_refinements"]
        if row.get("candidate_set_refs")
    ]
    assert binding_refinements
    for refinement in binding_refinements:
        assert refinement["refinement_delta"]["candidate_set_refs"]
        assert "antecedent_unresolved" in refinement["resulting_factor"]["residuals"]
        assert any(
            alternative["type_ref"] == "semantic.binding_candidate_set"
            for alternative in refinement["resulting_factor"]["alternatives"]
        )
        assert refinement["rejected_candidate_refs"] == []
