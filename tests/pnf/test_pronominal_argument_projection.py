from __future__ import annotations

from src.pnf.pronominal_argument_projection import (
    PRONOMINAL_ARGUMENT_PROJECTION_CONTRACT,
    project_parser_pronominal_arguments,
)
from src.pnf.reference_binding import project_pronominal_reference_arguments


def test_parser_observation_produces_generic_pronominal_argument_and_candidates() -> None:
    factors = project_parser_pronominal_arguments(
        document_ref="document:pronoun",
        parser_observations=(
            {
                "observation_ref": "parser-observation:1",
                "span_ref": "span:1",
                "upos": "PRON",
                "dependency": "nsubj",
                "dependency_ref": "dependency:1",
                "morphology": {"Person": ["3"], "Number": ["Sing"]},
                "source_factor_ref": "factor:predicate",
            },
        ),
    )
    assert len(factors) == 1
    factor = factors[0]
    assert factor["factor_type"] == "semantic.argument_reference"
    assert factor["metadata"]["parser_pos"] == "PRON"
    assert factor["metadata"]["role"] == "subject"
    assert factor["metadata"]["source_factor_ref"] == "factor:predicate"
    assert "span:1" in factor["metadata"]["provenance_refs"]

    artifacts = project_pronominal_reference_arguments(
        {
            "pnf_graph": {
                "graph_ref": "graph:1",
                "document_ref": "document:pronoun",
                "factors": list(factors),
                "constraints": [],
                "relation_refs": [],
                "residuals": [],
            },
            "refined_pnf_graph": {
                "graph_ref": "graph:1",
                "document_ref": "document:pronoun",
                "factors": list(factors),
                "constraints": [],
                "relation_refs": [],
                "residuals": [],
            },
        }
    )
    projected = artifacts["refined_pnf_graph"]["factors"][0]
    types = {row["type_ref"] for row in projected["alternatives"]}
    assert "semantic.reference_candidate" in types
    assert artifacts["reference_argument_projection_summary"]["english_pronoun_catalogue_used"] is False


def test_non_pronoun_observation_is_not_projected() -> None:
    assert project_parser_pronominal_arguments(
        document_ref="document:pronoun",
        parser_observations=(
            {
                "observation_ref": "parser-observation:2",
                "span_ref": "span:2",
                "upos": "NOUN",
            },
        ),
    ) == ()
