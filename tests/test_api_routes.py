import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.api.sample_routes import (
    api_logic_tree_search,
    api_provision,
    api_subgraph,
    api_treatment,
)


def test_subgraph_endpoint():
    data = api_subgraph("example text")
    assert "cloud" in data
    assert "tokens" in data
    assert data["tokens"], "expected at least one token"
    first = data["tokens"][0]
    assert {"text", "lemma_", "pos_", "morph", "idx", "class_"}.issubset(first)
    assert first["class_"] is None


def test_treatment_endpoint():
    data = api_treatment("a person shall act")
    assert "rules" in data


def test_provision_endpoint():
    data = api_provision("Sample provision text")
    assert "provision" in data


def test_logic_tree_search_endpoint(tmp_path):
    from src import logic_tree

    db_path = tmp_path / "logic_tree.sqlite"
    tokens = [
        logic_tree.PipelineToken(text="A", lemma="a", pos="DET", dep="", ent_type=""),
        logic_tree.PipelineToken(text="person", lemma="person", pos="NOUN", dep="", ent_type=""),
        logic_tree.PipelineToken(text="must", lemma="must", pos="AUX", dep="", ent_type=""),
        logic_tree.PipelineToken(text="comply", lemma="comply", pos="VERB", dep="ROOT", ent_type=""),
    ]
    tree = logic_tree.build(tokens, source_id="doc-fts-api")
    conn = sqlite3.connect(db_path)
    try:
        logic_tree.prepare_logic_tree_schema(conn)
        logic_tree.project_logic_tree_to_sqlite(tree, conn, doc_id="doc-fts-api")
        logic_tree.index_tokens_for_fts(conn, doc_id="doc-fts-api", tokens=tokens)
    finally:
        conn.close()

    data = api_logic_tree_search("must", sqlite_path=str(db_path), use_offsets=False)
    results = data["results"]
    assert results
    assert results[0]["doc_id"] == "doc-fts-api"
