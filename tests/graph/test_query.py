from datetime import date
from pathlib import Path

from src.graph.query import (
    load_graph,
    search_by_type,
    search_by_citation,
    search_by_tag,
    traverse_edges,
)


def _load() -> dict:
    path = Path(__file__).with_name("sample_graph.json")
    return load_graph(path)


def test_search_by_type():
    graph = _load()
    nodes = search_by_type(graph, "case")
    assert {n["id"] for n in nodes} == {"1", "3"}


def test_search_by_citation():
    graph = _load()
    nodes = search_by_citation(graph, "CIT2")
    assert nodes[0]["id"] == "2"


def test_search_by_tag():
    graph = _load()
    nodes = search_by_tag(graph, "foo")
    assert {n["id"] for n in nodes} == {"1", "2"}


def test_traverse_edges_basic():
    graph = _load()
    result = traverse_edges(graph, "1", depth=2)
    assert {n["id"] for n in result["nodes"]} == {"1", "2", "3"}
    assert len(result["edges"]) == 2


def test_traverse_edges_filters():
    graph = _load()
    result = traverse_edges(graph, "1", depth=2, since=date(2021, 1, 1))
    assert {n["id"] for n in result["nodes"]} == {"1"}
    assert result["edges"] == []
    result2 = traverse_edges(graph, "1", depth=2, min_weight=0.6)
    assert {n["id"] for n in result2["nodes"]} == {"1"}
    assert result2["edges"] == []
