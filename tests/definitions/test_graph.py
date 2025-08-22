import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))

from src.definitions import DefinitionGraph


def test_cyclic_definitions_do_not_loop():
    defs = {
        "a": ["b"],
        "b": ["c"],
        "c": ["a"],
    }
    graph = DefinitionGraph(defs)
    result = graph.expand("a", depth=10)
    assert result == {
        "a": ["b"],
        "b": ["c"],
        "c": ["a"],
    }


def test_expansion_is_deterministic():
    defs = {
        "a": ["b"],
        "b": ["c"],
        "c": ["a"],
    }
    graph = DefinitionGraph(defs)
    first = graph.expand("a", depth=5)
    second = graph.expand("a", depth=5)
    assert first == second
