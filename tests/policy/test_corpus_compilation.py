from __future__ import annotations

from pathlib import Path
import shutil

import pytest

from src.policy.corpus_compilation import (
    build_corpus_manifest,
    compile_directory,
    default_compiler_context,
)


FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "corpora" / "gwb-mini"
AU_FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "corpora" / "au-mini"


def test_directory_kernel_compiles_fixture_without_network_or_cross_document_closure(
    tmp_path,
):
    corpus = tmp_path / "corpus"
    shutil.copytree(FIXTURE_DIR, corpus)
    output = corpus / "artifacts"

    result = compile_directory(
        corpus,
        context=default_compiler_context(),
        output_store=output,
    )

    assert result["summary"]["compiled_document_count"] == 3
    assert result["summary"]["unsupported_document_count"] == 1
    assert result["summary"]["network_performed"] is False
    assert result["summary"]["cross_document_identity_closed"] is False
    assert (output / "manifest.json").is_file()
    assert (output / "corpus" / "demand-groups.json").is_file()
    assert all(
        row["artifacts"]["phase_boundary"]["readiness_invoked"] is False
        for row in result["compilations"]
        if row["status"] == "compiled"
    )


def test_directory_kernel_is_deterministic_and_append_only_on_rerun(tmp_path):
    corpus = tmp_path / "corpus"
    shutil.copytree(FIXTURE_DIR, corpus)
    output = tmp_path / "artifacts"

    first = compile_directory(
        corpus, context=default_compiler_context(), output_store=output
    )
    second = compile_directory(
        corpus, context=default_compiler_context(), output_store=output
    )

    assert first["manifest"]["manifest_sha256"] == second["manifest"]["manifest_sha256"]
    assert first["summary"]["summary_sha256"] == second["summary"]["summary_sha256"]
    assert first["demand_groups"] == second["demand_groups"]


def test_inventory_uses_content_identity_and_preserves_duplicate_occurrences(tmp_path):
    (tmp_path / "a.txt").write_text("Bush", encoding="utf-8")
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "b.txt").write_text("Bush", encoding="utf-8")

    manifest = build_corpus_manifest(tmp_path, context=default_compiler_context())
    rows = manifest.to_dict()["ordered_documents"]

    assert [row["relative_path"] for row in rows] == ["a.txt", "nested/b.txt"]
    assert rows[0]["document_ref"] == rows[1]["document_ref"]
    assert rows[0]["relative_path"] != rows[1]["relative_path"]

    result = compile_directory(
        tmp_path,
        context=default_compiler_context(),
        output_store=tmp_path / "artifacts",
    )
    assert result["summary"]["compiled_document_count"] == 1


def test_invalid_text_isolated_and_remainder_compiles(tmp_path):
    (tmp_path / "good.txt").write_text("Bush met Bush.", encoding="utf-8")
    (tmp_path / "bad.txt").write_bytes(b"\xff\xfe")
    output = tmp_path / "artifacts"

    result = compile_directory(
        tmp_path, context=default_compiler_context(), output_store=output
    )

    assert result["summary"]["compiled_document_count"] == 1
    assert result["summary"]["failed_document_count"] == 1
    failed = next(row for row in result["compilations"] if row["status"] != "compiled")
    assert failed["status"] == "normalisation_failed"


def test_existing_output_rejects_changed_manifest(tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    source = corpus / "source.txt"
    source.write_text("first", encoding="utf-8")
    output = tmp_path / "artifacts"
    compile_directory(corpus, context=default_compiler_context(), output_store=output)
    source.write_text("second", encoding="utf-8")

    with pytest.raises(ValueError, match="append-only artifact differs"):
        compile_directory(
            corpus, context=default_compiler_context(), output_store=output
        )


def test_local_recurrence_refines_only_the_local_obligation(tmp_path):
    (tmp_path / "source.txt").write_text("Bush met Bush.", encoding="utf-8")
    result = compile_directory(
        tmp_path,
        context=default_compiler_context(),
        output_store=tmp_path / "artifacts",
    )
    compilation = next(
        row for row in result["compilations"] if row["status"] == "compiled"
    )
    meets = compilation["artifacts"]["typed_meets"]
    refinements = compilation["artifacts"]["factor_refinements"]
    plan = compilation["artifacts"]["local_meet_plan"]

    assert any(row["state"] == "compatible_with_refinement" for row in meets)
    assert plan
    assert any(
        "document_local_recurrence_unchecked" in row["prior_factor"]["residuals"]
        and "document_local_recurrence_unchecked"
        not in row["resulting_factor"]["residuals"]
        and row["resulting_factor"]["residuals"]
        for row in refinements
    )


def test_second_proof_corpus_uses_the_same_generic_semantic_reductions(tmp_path):
    corpus = tmp_path / "corpus"
    shutil.copytree(AU_FIXTURE_DIR, corpus)

    result = compile_directory(
        corpus,
        context=default_compiler_context(),
        output_store=tmp_path / "artifacts",
    )

    compilation = next(
        row for row in result["compilations"] if row["status"] == "compiled"
    )
    factor_types = {
        row["factor_type"] for row in compilation["artifacts"]["pnf_graph"]["factors"]
    }
    declarations = compilation["artifacts"]["semantic_reduction_declarations"]
    assert "semantic.eventuality" in factor_types
    assert "grammar:semantic:predicate:v0_4" in {
        row["declaration_ref"] for row in declarations
    }


def test_public_relation_roles_improve_local_types_without_external_identity(tmp_path):
    (tmp_path / "source.txt").write_text("Ada met Bob in July.", encoding="utf-8")

    result = compile_directory(
        tmp_path,
        context=default_compiler_context(),
        output_store=tmp_path / "artifacts",
    )
    compilation = next(
        row for row in result["compilations"] if row["status"] == "compiled"
    )
    hypotheses = compilation["artifacts"]["structural_type_hypotheses"]
    local_types = compilation["artifacts"]["local_typing"]["local_type_alternatives"]

    assert hypotheses
    assert any(
        row["local_type"]
        in {"linguistic_predicate", "modified_nominal_head", "nominal_modifier"}
        for row in hypotheses
    )
    assert any(
        row["derivation_basis"] == "declared_relational_projection"
        for row in local_types
    )
    assert all("external_identity" not in row["local_type"] for row in local_types)
    assert "unresolved_span_diagnostic_summary" in compilation["artifacts"]


def test_compiler_persists_one_public_parser_observation_graph(tmp_path):
    (tmp_path / "source.txt").write_text("He spoke. Bush resigned.", encoding="utf-8")

    result = compile_directory(
        tmp_path,
        context=default_compiler_context(),
        output_store=tmp_path / "artifacts",
    )
    compilation = next(
        row for row in result["compilations"] if row["status"] == "compiled"
    )
    artifacts = compilation["artifacts"]
    parser_receipt = artifacts["parser_receipt"]
    semantic_layer = artifacts["semantic_annotation_layer"]
    annotation_types = {
        row["annotation_type"] for row in semantic_layer["token_annotations"]
    }
    relation_types = {
        row["relation_type"] for row in semantic_layer["relation_annotations"]
    }
    predicate_factors = [
        row
        for row in artifacts["pnf_graph"]["factors"]
        if row["factor_type"] == "semantic.eventuality"
    ]

    assert parser_receipt["backend_ref"] == "parser:spacy"
    assert {"parser.pos", "parser.morphology", "parser.dependency"}.issubset(
        annotation_types
    )
    assert {"parser.dependency_head", "parser.capability_receipt"}.issubset(
        relation_types
    )
    assert predicate_factors
    assert artifacts["relational_bundle"]["relations"]


def test_local_binding_candidates_refine_pronominal_arguments_without_identity(
    tmp_path,
):
    (tmp_path / "source.txt").write_text("Bush entered. He spoke.", encoding="utf-8")
    result = compile_directory(
        tmp_path,
        context=default_compiler_context(),
        output_store=tmp_path / "artifacts",
    )
    artifacts = next(
        row["artifacts"]
        for row in result["compilations"]
        if row["status"] == "compiled"
    )

    binding_evidence = [
        row
        for row in artifacts["local_evidence"]
        if row["evidence_type"] == "typed_binding_candidate"
    ]
    assert any(
        row["relation"] == "possible_coreference_with" for row in binding_evidence
    )
    assert any(
        row["relation"] == "binding_incompatible_with" for row in binding_evidence
    )
    refinement = next(
        row
        for row in artifacts["factor_refinements"]
        if any(
            ":binding:entity_reference:" in ref for ref in row["added_alternative_refs"]
        )
    )
    assert "antecedent_unresolved" in refinement["resulting_factor"]["residuals"]
    assert refinement["rejected_candidate_refs"]
    assert all(
        row["authority"] == "assessment_only"
        for row in artifacts["constraint_assessments"]
    )


def test_event_anaphora_and_expletive_branches_do_not_become_entity_identity(tmp_path):
    (tmp_path / "source.txt").write_text(
        "Bush resigned. It shocked observers. It was raining.", encoding="utf-8"
    )
    result = compile_directory(
        tmp_path,
        context=default_compiler_context(),
        output_store=tmp_path / "artifacts",
    )
    artifacts = next(
        row["artifacts"]
        for row in result["compilations"]
        if row["status"] == "compiled"
    )

    binding_evidence = [
        row
        for row in artifacts["local_evidence"]
        if row["evidence_type"] == "typed_binding_candidate"
    ]
    assert any(
        row["relation"] == "possible_eventuality_reference" for row in binding_evidence
    )
    reference_factors = [
        row
        for row in artifacts["refined_pnf_graph"]["factors"]
        if row["factor_type"] == "semantic.argument.subject"
        and any(
            alternative["type_ref"] == "semantic.reference_candidate"
            for alternative in row["alternatives"]
        )
    ]
    assert any(
        any(
            alternative["value"].get("referential_type") == "expletive_realisation"
            for alternative in row["alternatives"]
            if isinstance(alternative["value"], dict)
        )
        for row in reference_factors
    )
    local_demands = [
        row
        for row in artifacts["resolution_demands"]
        if row["budget"] == "bounded_document_local_evidence"
    ]
    assert local_demands
    assert all(
        set(row["requested_facets"]).issubset(
            {
                "antecedent_unresolved",
                "referential_type_unresolved",
                "grammatical_subject_semantic_status_unresolved",
            }
        )
        for row in local_demands
    )


def test_passive_subject_role_refinement_never_adds_agent(tmp_path):
    (tmp_path / "source.txt").write_text("Bush was warned.", encoding="utf-8")
    result = compile_directory(
        tmp_path,
        context=default_compiler_context(),
        output_store=tmp_path / "artifacts",
    )
    artifacts = next(
        row["artifacts"]
        for row in result["compilations"]
        if row["status"] == "compiled"
    )
    refined_subject = next(
        row
        for row in artifacts["refined_pnf_graph"]["factors"]
        if row["factor_type"] == "semantic.argument.subject"
    )
    role_values = {
        alternative["value"].get("semantic_role")
        for alternative in refined_subject["alternatives"]
        if alternative["type_ref"] == "semantic.role_candidate"
    }
    assert role_values == {"patient", "theme"}
    assert "semantic_role_unresolved" in refined_subject["residuals"]
