from src.language import (
    LocalTypeProjection,
    SemanticReductionDeclaration,
    default_semantic_reduction_declarations,
    diagnose_untyped_mentions,
    derive_relational_type_hypotheses,
    reduce_relational_bundle,
)


def test_generic_relation_reductions_preserve_eventuality_and_argument_factors():
    output = reduce_relational_bundle(
        document_ref="document:fixture",
        atom_span_refs={
            "a1": "span:person",
            "a2": "span:predicate",
            "a3": "span:object",
        },
        declarations=default_semantic_reduction_declarations(),
        bundle={
            "relations": [
                {
                    "id": "e1",
                    "type": "predicate",
                    "roles": [
                        {"role": "head", "atom": "a2"},
                        {"role": "subject", "atom": "a1"},
                        {"role": "object", "atom": "a3"},
                    ],
                },
                {
                    "id": "e2",
                    "type": "temporal",
                    "roles": [{"role": "anchor", "atom": "a3"}],
                },
            ]
        },
    )

    kinds = {factor.factor_type for factor in output.factors}
    assert "semantic.eventuality" in kinds
    assert "semantic.argument.subject" in kinds
    assert "semantic.argument.object" in kinds
    assert "semantic.temporal_expression" in kinds
    assert all("identity" not in factor.factor_type for factor in output.factors)

    constraint_types = {row.constraint_type for row in output.constraints}
    assert {
        "syntactic_subject_of",
        "syntactic_object_of",
    }.issubset(constraint_types)
    assert all(
        row.source_factor_refs
        and row.target_factor_refs
        and row.payload["source_factor_ref"]
        and row.payload["target_factor_ref"]
        for row in output.constraints
    )


def test_reduction_declarations_are_generic_and_deterministic():
    declarations = default_semantic_reduction_declarations()

    assert [row.declaration_ref for row in declarations] == [
        "grammar:semantic:predicate:v0_4",
        "grammar:semantic:temporal:v0_3",
        "grammar:semantic:spatial:v0_3",
        "grammar:semantic:coordination:v0_3",
        "grammar:semantic:modification:v0_3",
        "grammar:semantic:composition:v0_4",
    ]
    assert not any(
        "gwb" in row.declaration_ref or "au" in row.declaration_ref
        for row in declarations
    )


def test_relational_type_hypotheses_preserve_role_branches_without_identity():
    hypotheses = derive_relational_type_hypotheses(
        atom_mention_refs={
            "a1": ("mention:subject",),
            "a2": ("mention:predicate",),
            "a3": ("mention:time",),
        },
        bundle={
            "relations": [
                {
                    "id": "e1",
                    "type": "predicate",
                    "roles": [
                        {"role": "head", "atom": "a2"},
                        {"role": "subject", "atom": "a1"},
                    ],
                },
                {
                    "id": "e2",
                    "type": "temporal",
                    "roles": [{"role": "anchor", "atom": "a3"}],
                },
            ]
        },
    )

    assert [
        (row["mention_ref"], row["semantic_family"], row["local_type"])
        for row in hypotheses
    ] == [
        ("mention:predicate", "eventuality", "linguistic_predicate"),
        ("mention:subject", "relation", "predicate_subject_role"),
        ("mention:time", "time", "temporal_anchor"),
    ]
    assert all("identity" not in str(row) for row in hypotheses)


def test_relational_type_hypotheses_follow_declarations_not_a_hidden_role_map():
    declarations = (
        SemanticReductionDeclaration(
            declaration_ref="grammar:test:v0_1",
            relation_type="predicate",
            output_factor_type="semantic.eventuality",
            output_type_ref="semantic.eventuality_candidate",
            local_type_projections=(
                LocalTypeProjection("head", "eventuality", "declared_predicate"),
            ),
        ),
    )

    hypotheses = derive_relational_type_hypotheses(
        declarations=declarations,
        atom_mention_refs={"a1": ("mention:predicate",)},
        bundle={
            "relations": [
                {
                    "id": "e1",
                    "type": "predicate",
                    "roles": [{"role": "head", "atom": "a1"}],
                }
            ]
        },
    )

    assert [(row["semantic_family"], row["local_type"]) for row in hypotheses] == [
        ("eventuality", "declared_predicate")
    ]
    assert hypotheses[0]["derivation_basis"] == "declared_relational_projection"


def test_pronominal_subject_becomes_an_unresolved_pnf_reference_branch():
    output = reduce_relational_bundle(
        document_ref="document:fixture",
        atom_span_refs={"a1": "span:pronoun", "a2": "span:speak"},
        declarations=default_semantic_reduction_declarations(),
        bundle={
            "atoms": [
                {
                    "id": "a1",
                    "text": "He",
                    "pos": "PRON",
                    "morph": {"Person": ["3"], "Number": ["Sing"]},
                }
            ],
            "relations": [
                {
                    "id": "e1",
                    "type": "predicate",
                    "roles": [
                        {"role": "head", "atom": "a2"},
                        {"role": "subject", "atom": "a1"},
                    ],
                }
            ],
        },
    )

    subject = next(
        factor
        for factor in output.factors
        if factor.factor_type == "semantic.argument.subject"
    )
    assert {alternative.type_ref for alternative in subject.alternatives} == {
        "semantic.argument_candidate",
        "semantic.reference_candidate",
    }
    assert set(subject.residuals) == {
        "antecedent_unresolved",
        "grammatical_subject_semantic_status_unresolved",
        "referential_type_unresolved",
        "syntactic_argument_structure_unchecked",
    }


def test_clausal_composition_keeps_embedded_content_distinct_from_truth():
    output = reduce_relational_bundle(
        document_ref="document:fixture",
        atom_span_refs={"a1": "span:said", "a2": "span:changed"},
        declarations=default_semantic_reduction_declarations(),
        bundle={
            "relations": [
                {
                    "id": "e1",
                    "type": "composition",
                    "roles": [
                        {"role": "host", "atom": "a1"},
                        {"role": "content", "atom": "a2"},
                    ],
                }
            ]
        },
    )

    proposition = next(
        factor
        for factor in output.factors
        if factor.factor_type == "semantic.embedded_proposition"
    )
    assert set(proposition.residuals) == {
        "composition_scope_unresolved",
        "proposition_truth_not_evaluated",
    }
    assert {constraint.constraint_type for constraint in output.constraints} == {
        "host_of_embedded_proposition",
        "content_of",
    }


def test_untyped_diagnostic_distinguishes_observed_structure_from_parser_absence():
    diagnostics = diagnose_untyped_mentions(
        mentions=(
            {"mention_ref": "mention:head"},
            {"mention_ref": "mention:bare"},
        ),
        local_typing={
            "coverage_pressure": (
                {"mention_ref": "mention:head", "coverage_state": "untyped"},
                {"mention_ref": "mention:bare", "coverage_state": "untyped"},
            ),
            "forms": (),
        },
        atom_mention_refs={"a1": ("mention:head",)},
        bundle={
            "relations": [
                {
                    "id": "e1",
                    "type": "modifier",
                    "roles": [{"role": "head", "atom": "a1"}],
                }
            ]
        },
    )

    assert [row["annotation_shape"] for row in diagnostics] == [
        "parser_observation_absent",
        "nominal_head_available",
    ]
    assert diagnostics[1]["missing_reduction_capability"] == "nominal_description"
    assert all(row["authority"] == "diagnostic_only" for row in diagnostics)


def test_untyped_diagnostic_partitions_actionable_missing_annotation_causes():
    diagnostics = diagnose_untyped_mentions(
        mentions=(
            {"mention_ref": "mention:align", "span_alignment": "mismatch"},
            {"mention_ref": "mention:boundary", "boundary_state": "overbroad"},
            {"mention_ref": "mention:word"},
        ),
        local_typing={
            "coverage_pressure": tuple(
                {"mention_ref": ref, "coverage_state": "untyped"}
                for ref in ("mention:align", "mention:boundary", "mention:word")
            ),
            "forms": (),
        },
        atom_mention_refs={},
        bundle={"relations": ()},
    )

    assert [row["suppression_reason"] for row in diagnostics] == [
        "tokenization_or_alignment_mismatch",
        "mention_boundary_mismatch",
        "no_parser_observation",
    ]
    assert [row["missing_reduction_capability"] for row in diagnostics] == [
        "alignment",
        "boundary",
        "semantically_weak_or_unobserved",
    ]


def test_untyped_diagnostic_records_projected_unconsumed_parser_observations():
    diagnostics = diagnose_untyped_mentions(
        mentions=({"mention_ref": "mention:pronoun"},),
        local_typing={
            "coverage_pressure": (
                {"mention_ref": "mention:pronoun", "coverage_state": "untyped"},
            ),
            "forms": (),
        },
        atom_mention_refs={},
        bundle={"relations": ()},
        parser_observation_refs={"mention:pronoun": ("parser-token:1",)},
        parser_capabilities={"tokenization": True, "morphology": True},
    )

    assert diagnostics[0]["annotation_shape"] == "parser_observation_unconsumed"
    assert (
        diagnostics[0]["missing_reduction_capability"]
        == "reduction_declaration_missing"
    )
    assert diagnostics[0]["parser_observation_refs"] == ("parser-token:1",)
    assert diagnostics[0]["projection_state"] == "projected"
