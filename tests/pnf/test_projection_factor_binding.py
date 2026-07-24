from __future__ import annotations

from src.pnf.projection_factor_binding import bind_projection_factor_rows


def test_reduced_summary_projects_through_persisted_source_factor() -> None:
    proposal = {
        "proposal_ref": "proposal:1",
        "candidate_payload": {"source_factor_ref": "factor:source"},
        "source_span_refs": ["span:1"],
        "input_observation_refs": ["observation:1"],
        "dependency_factor_refs": [],
        "transport_refs": [],
        "ontology_axis_refs": ["axis:legal"],
    }
    reduced = {
        "factor_ref": "fibre-summary:1",
        "semantic_coordinate_ref": "coordinate:1",
        "fibre_kind": "hypothesis",
        "factor_type_ref": "semantic.legal_authority",
        "structural_signature": "signature:authority:v1",
        "proposal_refs": ["proposal:1"],
        "role_bindings": {
            "authority": "source:act",
            "jurisdiction": "AU-QLD",
        },
        "qualifier_state": {},
        "residuals": [],
        "ontology_axis_refs": ["axis:legal"],
        "transport_refs": [],
        "support_states": ["supported"],
    }
    source = {
        "factor_ref": "factor:source",
        "factor_type": "semantic.legal_authority",
        "alternatives": [],
        "constraints": [],
        "residuals": [],
        "closure_state": "locally_closed",
        "metadata": {"factor_revision_ref": "revision:source"},
    }

    bound = bind_projection_factor_rows(
        reduced_factors=(reduced,),
        proposals=(proposal,),
        graph_factors=(source,),
    )

    assert len(bound) == 1
    row = bound[0]
    assert row["factor_ref"] == "factor:source"
    assert row["metadata"]["fibre_summary_ref"] == "fibre-summary:1"
    assert row["metadata"]["semantic_coordinate_ref"] == "coordinate:1"
    assert row["metadata"]["role_bindings"]["jurisdiction"] == "AU-QLD"
    assert row["metadata"]["projection_factor_binding"] == (
        "persisted_source_factor"
    )
    assert "span:1" in row["metadata"]["provenance_refs"]


def test_new_composed_summary_retains_its_own_factor_ref() -> None:
    reduced = {
        "factor_ref": "factor:new-composed",
        "semantic_coordinate_ref": "coordinate:new",
        "fibre_kind": "composition",
        "factor_type_ref": "semantic.legal_exception",
        "structural_signature": "signature:exception:v1",
        "proposal_refs": ["proposal:new"],
        "role_bindings": {"host": "factor:norm"},
        "qualifier_state": {},
        "residuals": [],
    }
    proposal = {
        "proposal_ref": "proposal:new",
        "candidate_payload": {},
    }

    bound = bind_projection_factor_rows(
        reduced_factors=(reduced,),
        proposals=(proposal,),
        graph_factors=(),
    )

    assert bound == (reduced,)
