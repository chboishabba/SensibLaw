from src.graph.inference import infer_semantic_recommendations
from src.graph.models import GraphNode, LegalGraph, NodeType


def test_infer_semantic_recommendations_scores_keywords():
    graph = LegalGraph()
    graph.add_node(
        GraphNode(
            type=NodeType.CASE,
            identifier="case:negligence",
            metadata={"summary": "A negligent act caused injury requiring compensation"},
        )
    )
    graph.add_node(
        GraphNode(
            type=NodeType.PROVISION,
            identifier="prov:1",
            metadata={"text": "damages and injunctions"},
        )
    )

    recommendations = infer_semantic_recommendations(
        graph,
        wrong_type_catalog={"negligence": ["negligent"]},
        protected_interest_catalog={"bodily_integrity": ["injury"]},
        remedy_catalog={"compensation": ["compensation"], "injunction": ["injunction"]},
    )

    assert recommendations.wrong_types[0].identifier == "negligence"
    assert recommendations.protected_interests[0].identifier == "bodily_integrity"
    assert any(rec.node_type == NodeType.EVENT for rec in recommendations.events)
    assert recommendations.remedies[0].identifier in {"compensation", "injunction"}
