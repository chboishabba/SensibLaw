import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.graph.models import CaseNode, GraphNode, LegalGraph, NodeType  # noqa: E402
from src.graph.tircorder import (  # noqa: E402
    MissingNodeError,
    NodeTypeMismatchError,
    TiRCorderBuilder,
    applies_to,
    articulates,
    build_tircorder_edges,
    controls,
    has_element,
    interprets,
)


@pytest.fixture()
def graph() -> LegalGraph:
    graph = LegalGraph()
    graph.add_node(
        CaseNode(
            identifier="case-1",
            metadata={},
            date=None,
            court_rank=1,
        )
    )
    graph.add_node(
        CaseNode(
            identifier="case-2",
            metadata={},
            date=None,
            court_rank=1,
        )
    )
    graph.add_node(GraphNode(type=NodeType.CONCEPT, identifier="concept-1"))
    graph.add_node(GraphNode(type=NodeType.CONCEPT, identifier="concept-2"))
    graph.add_node(GraphNode(type=NodeType.PROVISION, identifier="prov-1"))
    return graph


def test_builder_emits_edges(graph: LegalGraph) -> None:
    builder = TiRCorderBuilder(graph)

    art_edge = builder.articulates(case_id="case-1", concept_id="concept-1")
    has_edge = builder.has_element(concept_id="concept-1", element_id="concept-2")
    applies_edge = builder.applies_to(concept_id="concept-1", provision_id="prov-1")
    interp_edge = builder.interprets(case_id="case-1", provision_id="prov-1")
    control_edge = builder.controls(leading_case_id="case-1", following_case_id="case-2")

    assert art_edge.type.name == "ARTICULATES"
    assert has_edge.type.name == "HAS_ELEMENT"
    assert applies_edge.type.name == "APPLIES_TO"
    assert interp_edge.type.name == "INTERPRETS"
    assert control_edge.type.name == "CONTROLS"
    assert graph.edges[-5:] == [
        art_edge,
        has_edge,
        applies_edge,
        interp_edge,
        control_edge,
    ]


def test_module_wrappers(graph: LegalGraph) -> None:
    articulates(graph, case_id="case-1", concept_id="concept-2", metadata={"source": "headnote"})
    has_element(graph, concept_id="concept-2", element_id="concept-1", weight=2.0)
    applies_to(graph, concept_id="concept-2", provision_id="prov-1", weight=0.5)
    interprets(graph, case_id="case-2", provision_id="prov-1")
    controls(graph, leading_case_id="case-2", following_case_id="case-1")

    assert graph.edges[-5].metadata == {"source": "headnote"}
    assert pytest.approx(graph.edges[-4].weight) == 2.0
    assert pytest.approx(graph.edges[-3].weight) == 0.5


def test_bulk_builder(graph: LegalGraph) -> None:
    build_tircorder_edges(
        graph,
        articulates=[{"case_id": "case-1", "concept_id": "concept-1"}],
        has_elements=[{"concept_id": "concept-1", "element_id": "concept-2"}],
        applies_to=[{"concept_id": "concept-2", "provision_id": "prov-1"}],
        interprets=[{"case_id": "case-2", "provision_id": "prov-1"}],
        controls=[{"leading_case_id": "case-1", "following_case_id": "case-2"}],
    )

    assert graph.edges[-5].type.name == "ARTICULATES"
    assert graph.edges[-4].type.name == "HAS_ELEMENT"
    assert graph.edges[-3].type.name == "APPLIES_TO"
    assert graph.edges[-2].type.name == "INTERPRETS"
    assert graph.edges[-1].type.name == "CONTROLS"


def test_missing_node(graph: LegalGraph) -> None:
    builder = TiRCorderBuilder(graph)
    with pytest.raises(MissingNodeError):
        builder.articulates(case_id="case-x", concept_id="concept-1")


def test_type_validation(graph: LegalGraph) -> None:
    builder = TiRCorderBuilder(graph)
    graph.add_node(GraphNode(type=NodeType.DOCUMENT, identifier="case-doc"))
    with pytest.raises(NodeTypeMismatchError):
        builder.controls(leading_case_id="case-doc", following_case_id="case-1")
