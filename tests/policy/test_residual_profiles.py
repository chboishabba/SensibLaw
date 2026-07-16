from __future__ import annotations

from src.policy.domain_pressure import build_pressure_assessment
from src.policy.residual_graph import build_typed_residual_graph
from src.policy.residual_profiles import build_typed_residual_profile
from src.policy.review_packet_projection import build_review_packet_projection


def _assessment(*, candidate_ref: str, target_state: str = "partial") -> dict:
    return build_pressure_assessment(
        candidate_ref=candidate_ref,
        domain_invariant_ref="domain:example:v1",
        coverage_state="observed",
        review_disposition="B",
        residuals=[
            {
                "residual_kind": "target_model",
                "state": target_state,
                "expected": {"property": "P2"},
                "observed": {"property": "P1"},
            },
            {
                "residual_kind": "split_structure",
                "state": "partial",
                "expected": {"one": "statement"},
                "observed": {"many": "periods"},
            },
        ],
    )


def _context(**overrides: object) -> dict[str, object]:
    context = {
        "entity_kind_compatible": True,
        "relation_compatible": True,
        "temporal_compatible": True,
        "source_pnf_compatible": True,
        "superclass_compatible": True,
        "disjointness_clear": True,
    }
    context.update(overrides)
    return context


def test_profile_projects_packet_without_authority() -> None:
    profile = build_typed_residual_profile(
        assessment=_assessment(candidate_ref="candidate:1"),
        context=_context(),
        source_revision_ref="source:Q1@1",
        source_anchor_refs=["Q1$abc"],
    )
    packet = build_review_packet_projection(
        residual_profile=profile,
        candidate_record={
            "entity_qid": "Q1",
            "source_statement_id": "Q1$abc",
            "classification": "split_required",
            "subject_family": "company",
            "ghg_semantic_family": "organisation_emissions",
            "split_axes": [{"property": "P585", "cardinality": 2}],
            "claim_bundle_before": {
                "subject": "Q1",
                "property": "P1",
                "qualifiers": {"P585": ["2022", "2023"]},
                "references": [{"P854": ["https://example.test"]}],
            },
            "claim_bundle_after": {
                "subject": "Q1",
                "property": "P2",
                "qualifiers": {"P585": ["2022", "2023"]},
                "references": [{"P854": ["https://example.test"]}],
            },
        },
        source_revision_ref="source:Q1@1",
        source_anchor_refs=["Q1$abc"],
    )

    assert profile["comparison_state"] == "admissible"
    assert packet["review_kind"] == "decomposition"
    assert packet["confirmation_choices"] == [
        "confirm_split_plan",
        "reject_split_plan",
        "request_revised_split",
        "hold_unresolved",
    ]
    assert packet["authority"] == "review_packet_only"
    assert packet["promotion_effect"] == "not_evaluated"
    assert packet["qualifier_reference_carry_plan"]["preserve_exactly"] is True


def test_profile_projects_a_family_conflict_packet_without_split_choices() -> None:
    profile = build_typed_residual_profile(
        assessment=build_pressure_assessment(
            candidate_ref="candidate:conflict",
            domain_invariant_ref="domain:example:v1",
            coverage_state="observed",
            review_disposition="review_only",
            residuals=[
                {
                    "residual_kind": "scope_overlap",
                    "state": "contradictory",
                    "expected": {"scope_partition": "non_overlapping"},
                    "observed": {"statement_ids": ["Q1$a", "Q1$b"]},
                }
            ],
        ),
        context=_context(),
        source_revision_ref="source:Q1@1",
    )
    packet = build_review_packet_projection(
        residual_profile=profile,
        candidate_record={
            "entity_qid": "Q1",
            "source_statement_id": "Q1$a",
            "classification": "ambiguous_semantics",
            "claim_bundle_before": {"subject": "Q1", "qualifiers": {}},
            "claim_bundle_after": {"subject": "Q1", "qualifiers": {}},
            "statement_family_context": {
                "scope_partition_state": "overlapping",
                "total_component_relation": "no_total",
                "member_statement_ids": ["Q1$a", "Q1$b"],
            },
        },
        source_revision_ref="source:Q1@1",
    )

    assert packet["review_kind"] == "family_conflict"
    assert packet["confirmation_choices"] == [
        "confirm_hold",
        "request_reconstruction",
        "mark_legitimate_exception",
        "hold_unresolved",
    ]
    assert packet["conflict_evidence"][0]["residual_kind"] == "scope_overlap"


def test_safe_candidate_keeps_conformance_review_kind_with_visible_family_warning() -> (
    None
):
    profile = build_typed_residual_profile(
        assessment=build_pressure_assessment(
            candidate_ref="candidate:safe-with-warning",
            domain_invariant_ref="domain:example:v1",
            coverage_state="observed",
            review_disposition="A",
            residuals=[
                {
                    "residual_kind": "unknown_scope_partition",
                    "state": "partial",
                    "expected": {"scope_partition": "one scope per statement"},
                    "observed": {"scope_cardinality": 2},
                }
            ],
        ),
        context=_context(),
        source_revision_ref="source:Q1@1",
    )
    packet = build_review_packet_projection(
        residual_profile=profile,
        candidate_record={
            "entity_qid": "Q1",
            "source_statement_id": "Q1$a",
            "classification": "safe_with_reference_transfer",
            "claim_bundle_before": {"subject": "Q1", "qualifiers": {}},
            "claim_bundle_after": {"subject": "Q1", "qualifiers": {}},
            "statement_family_context": {
                "scope_partition_state": "overloaded",
                "total_component_relation": "not_comparable",
            },
        },
        source_revision_ref="source:Q1@1",
    )

    assert packet["review_kind"] == "model_conformance"
    assert packet["confirmation_choices"][0] == "confirm_model_conformant"
    assert packet["conflict_evidence"][0]["residual_kind"] == "unknown_scope_partition"


def test_graph_retains_similarity_incompatibility_mask_and_unknown() -> None:
    compatible = build_typed_residual_profile(
        assessment=_assessment(
            candidate_ref="candidate:compatible", target_state="exact"
        ),
        context=_context(),
        source_revision_ref="source:1",
    )
    similar = build_typed_residual_profile(
        assessment=_assessment(candidate_ref="candidate:similar", target_state="exact"),
        context=_context(),
        source_revision_ref="source:1b",
    )
    incompatible = build_typed_residual_profile(
        assessment=_assessment(
            candidate_ref="candidate:incompatible", target_state="contradictory"
        ),
        context=_context(),
        source_revision_ref="source:2",
    )
    masked = build_typed_residual_profile(
        assessment=_assessment(candidate_ref="candidate:masked"),
        context=_context(entity_kind_compatible=False),
        source_revision_ref="source:3",
    )
    unknown_assessment = _assessment(candidate_ref="candidate:unknown")
    unknown_assessment["coverage_state"] = "incomplete"
    unknown = build_typed_residual_profile(
        assessment=unknown_assessment,
        context=_context(),
        source_revision_ref="source:4",
    )

    graph = build_typed_residual_graph(
        [compatible, similar, incompatible, masked, unknown]
    )
    kinds = {edge["edge_kind"] for edge in graph["edges"]}

    assert kinds == {
        "positive_similarity",
        "negative_incompatibility",
        "masked_analogy",
        "unknown_due_to_coverage",
    }
    assert graph["authority"] == "diagnostic_only"
    assert graph["promotion_effect"] == "not_evaluated"


def test_graph_represents_an_empty_profile_selection() -> None:
    graph = build_typed_residual_graph([])

    assert graph["nodes"] == []
    assert graph["edges"] == []
    assert graph["summary"]["node_count"] == 0
    assert graph["authority"] == "diagnostic_only"
