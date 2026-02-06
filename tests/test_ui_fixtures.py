import json
from pathlib import Path

FORBIDDEN_TERMS = {
    "compliance",
    "breach",
    "prevails",
    "valid",
    "invalid",
    "stronger",
    "weaker",
    "satisfies",
    "violates",
    "binding",
    "override",
}

FIXTURE_DIR = Path("tests/fixtures/ui")


def _load(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def test_knowledge_graph_fixture_structure():
    data = _load("knowledge_graph_minimal.json")
    edges = data.get("edges", [])
    assert edges, "Fixture must include edges"
    assert data.get("nodes"), "Fixture must include nodes"
    for edge in edges:
        assert edge.get("citation"), "Edge missing citation"


def test_case_comparison_fixture_structure():
    data = _load("case_comparison_minimal.json")
    diff = data.get("diff", {})
    assert set(diff.get("added", [])) == {"OBL:3"}
    assert set(diff.get("removed", [])) == {"OBL:1"}
    assert set(diff.get("unchanged", [])) == {"OBL:2"}


def test_concepts_fixture_structure_and_language():
    data = _load("concepts_minimal.json")
    assert data.get("text")
    assert data.get("matches")
    serialized = json.dumps(data).lower()
    assert FORBIDDEN_TERMS.isdisjoint(serialized)


def test_obligations_fixture_structure_and_language():
    data = _load("obligations_minimal.json")
    assert data.get("results")
    serialized = json.dumps(data).lower()
    assert FORBIDDEN_TERMS.isdisjoint(serialized)
