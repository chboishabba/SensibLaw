from src.obligations import extract_obligations_from_text
from src.obligation_graph import build_obligation_graph


def test_graph_projection_is_deterministic():
    body = "The operator must keep records if requested."
    obs_a = extract_obligations_from_text(body, references=[], source_id="doc")
    obs_b = extract_obligations_from_text(body, references=[], source_id="doc")
    graph_a = build_obligation_graph(obs_a)
    graph_b = build_obligation_graph(obs_b)
    assert graph_a.nodes == graph_b.nodes
    assert graph_a.conditional_on == graph_b.conditional_on
    assert graph_a.exception_to == graph_b.exception_to


def test_no_inferred_edges_without_triggers():
    body = "The operator must keep records."
    graph = build_obligation_graph(extract_obligations_from_text(body, references=[], source_id="doc"))
    assert not graph.conditional_on
    assert not graph.exception_to


def test_exception_edge_created_from_explicit_text():
    body = "The operator must keep records unless exempt."
    graph = build_obligation_graph(extract_obligations_from_text(body, references=[], source_id="doc"))
    assert graph.exception_to
    assert graph.exception_to[0][1] == "unless"
