from src.pnf.factor_proposals import FactorProposal
from src.pnf.projection_factor_binding import bind_projection_factor_rows


def test_plural_reduced_summary_uses_durable_anchor_without_selecting_reading() -> None:
    proposals = (
        FactorProposal(
            document_ref="document:1",
            source_revision_ref="source:1",
            factor_type_ref="semantic.eventuality",
            source_span_refs=("span:1",),
            input_observation_refs=("observation:1",),
            dependency_factor_refs=(),
            structural_signature="signature:1",
            role_bindings={"actor": "entity:a"},
            qualifier_state={},
            producer_contract="test:producer",
            declaration_revision="v1",
            candidate_payload={"source_factor_ref": "factor:a"},
        ),
        FactorProposal(
            document_ref="document:1",
            source_revision_ref="source:1",
            factor_type_ref="semantic.eventuality",
            source_span_refs=("span:1",),
            input_observation_refs=("observation:1",),
            dependency_factor_refs=(),
            structural_signature="signature:1",
            role_bindings={"actor": "entity:b"},
            qualifier_state={},
            producer_contract="test:producer",
            declaration_revision="v1",
            candidate_payload={"source_factor_ref": "factor:b"},
        ),
    )
    bound = bind_projection_factor_rows(
        reduced_factors=(
            {
                "factor_ref": "fibre-summary:1",
                "proposal_refs": [row.proposal_ref for row in proposals],
                "structural_signature": "signature:1",
                "role_bindings": {},
                "qualifier_state": {},
            },
        ),
        proposals=tuple(row.to_dict() for row in proposals),
        graph_factors=(
            {
                "factor_ref": "factor:a",
                "factor_type": "semantic.eventuality",
                "metadata": {},
            },
            {
                "factor_ref": "factor:b",
                "factor_type": "semantic.eventuality",
                "metadata": {},
            },
        ),
    )
    assert bound[0]["factor_ref"] == "factor:a"
    assert bound[0]["metadata"]["source_factor_refs"] == ["factor:a", "factor:b"]
    assert (
        bound[0]["metadata"]["projection_factor_binding"]
        == "persisted_source_factor_anchor"
    )
