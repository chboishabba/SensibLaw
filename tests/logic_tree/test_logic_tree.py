from __future__ import annotations

import sqlite3

from src.logic_tree import (
    EdgeType,
    LogicTree,
    LOGIC_TREE_VERSION,
    NodeType,
    build,
    index_tokens_for_fts,
    prepare_logic_tree_schema,
    prepare_fts_schema,
    project_logic_tree_to_sqlite,
    rehydrate_logic_tree_from_sqlite,
    search_fts_over_logic_tree,
    walk_postorder,
    walk_preorder,
    walk_root_to_leaves,
)
from src.pipeline.tokens import Token
from src import pipeline


def test_build_handles_empty_tokens() -> None:
    tree = build([])

    assert isinstance(tree, LogicTree)
    assert tree.version == LOGIC_TREE_VERSION
    assert tree.root_id == "n0"
    assert [node.node_type for node in tree.nodes] == [NodeType.ROOT]
    assert tree.edges == []
    assert list(tree.to_dict()["nodes"]) == [{"id": "n0", "node_type": "ROOT", "span": None, "text": None, "source_id": "unknown"}]


def test_build_single_clause_sequences_tokens() -> None:
    tokens = [
        Token(text="A", lemma="a", pos="DET", dep="det", ent_type=""),
        Token(text="person", lemma="person", pos="NOUN", dep="nsubj", ent_type=""),
        Token(text="must", lemma="must", pos="AUX", dep="aux", ent_type=""),
        Token(text="not", lemma="not", pos="PART", dep="neg", ent_type=""),
        Token(text="enter", lemma="enter", pos="VERB", dep="ROOT", ent_type=""),
    ]

    tree = build(tokens, source_id="doc-1")

    assert tree.root_id == "n0"
    assert tree.nodes[0].node_type is NodeType.ROOT
    clause_nodes = [node for node in tree.nodes if node.node_type is NodeType.CLAUSE]
    assert len(clause_nodes) == 1
    clause = clause_nodes[0]
    assert clause.span == (0, len(tokens))
    assert clause.text == "A person must not enter"
    token_nodes = [node for node in tree.nodes if node.node_type not in (NodeType.ROOT, NodeType.CLAUSE)]
    assert [node.node_type for node in token_nodes] == [
        NodeType.TOKEN,
        NodeType.TOKEN,
        NodeType.MODAL,
        NodeType.TOKEN,
        NodeType.ACTION,
    ]
    # Edge types reflect modal/action mapping
    clause_edges = [edge for edge in tree.edges if edge.parent_id == clause.id]
    assert [edge.edge_type for edge in clause_edges] == [
        EdgeType.SEQUENCE,
        EdgeType.SEQUENCE,
        EdgeType.QUALIFIES,
        EdgeType.SEQUENCE,
        EdgeType.SEQUENCE,
    ]


def test_build_multi_clause_sequence() -> None:
    tokens = [
        Token(text="A", lemma="a", pos="DET", dep="", ent_type=""),
        Token(text="clause", lemma="clause", pos="NOUN", dep="", ent_type=""),
        Token(text="ends", lemma="end", pos="VERB", dep="ROOT", ent_type=""),
        Token(text=".", lemma=".", pos="PUNCT", dep="", ent_type=""),
        Token(text="Second", lemma="second", pos="ADJ", dep="", ent_type=""),
        Token(text="clause", lemma="clause", pos="NOUN", dep="", ent_type=""),
    ]

    tree = build(tokens, source_id="doc-2")

    clause_nodes = [node for node in tree.nodes if node.node_type is NodeType.CLAUSE]
    assert len(clause_nodes) == 2
    assert clause_nodes[0].span == (0, 4)
    assert clause_nodes[1].span == (4, 6)
    root_edges = [edge for edge in tree.edges if edge.parent_id == tree.root_id]
    assert [edge.child_id for edge in root_edges] == [clause_nodes[0].id, clause_nodes[1].id]


def test_build_qualifiers_and_exceptions_edge_types() -> None:
    tokens = [
        Token(text="A", lemma="a", pos="DET", dep="", ent_type=""),
        Token(text="person", lemma="person", pos="NOUN", dep="", ent_type=""),
        Token(text="must", lemma="must", pos="AUX", dep="", ent_type=""),
        Token(text="enter", lemma="enter", pos="VERB", dep="ROOT", ent_type=""),
        Token(text="if", lemma="if", pos="SCONJ", dep="", ent_type=""),
        Token(text="invited", lemma="invite", pos="VERB", dep="", ent_type=""),
        Token(text="unless", lemma="unless", pos="SCONJ", dep="", ent_type=""),
        Token(text="barred", lemma="bar", pos="VERB", dep="", ent_type=""),
    ]

    tree = build(tokens)
    clause_nodes = [node for node in tree.nodes if node.node_type is NodeType.CLAUSE]
    clause_edges = [edge for edge in tree.edges if edge.parent_id == clause_nodes[0].id]
    edge_types = [edge.edge_type for edge in clause_edges]
    assert EdgeType.QUALIFIES in edge_types  # modal
    assert EdgeType.DEPENDS_ON in edge_types  # condition
    assert EdgeType.EXCEPTS in edge_types  # exception


def test_traversal_orders_are_stable() -> None:
    tokens = [
        Token(text="A", lemma="a", pos="DET", dep="", ent_type=""),
        Token(text="person", lemma="person", pos="NOUN", dep="", ent_type=""),
        Token(text="must", lemma="must", pos="AUX", dep="", ent_type=""),
    ]
    tree = build(tokens)

    preorder_ids = [node.id for node in walk_preorder(tree)]
    postorder_ids = [node.id for node in walk_postorder(tree)]
    root_to_leaf_paths = [[node.id for node in path] for path in walk_root_to_leaves(tree)]

    assert preorder_ids == ["n0", "n1", "n2", "n3", "n4"]
    assert postorder_ids[-1] == "n0"
    assert root_to_leaf_paths == [["n0", "n1", "n2"], ["n0", "n1", "n3"], ["n0", "n1", "n4"]]


def test_build_is_deterministic() -> None:
    tokens = [
        Token(text="A", lemma="a", pos="DET", dep="", ent_type=""),
        Token(text="person", lemma="person", pos="NOUN", dep="", ent_type=""),
        Token(text="must", lemma="must", pos="AUX", dep="", ent_type=""),
    ]
    first = build(tokens)
    second = build(tokens)

    assert first.to_dict() == second.to_dict()
    assert first.to_dot() == second.to_dot()


def test_dot_snapshot_is_stable() -> None:
    tokens = [
        Token(text="A", lemma="a", pos="DET", dep="", ent_type=""),
        Token(text="person", lemma="person", pos="NOUN", dep="", ent_type=""),
    ]
    tree = build(tokens)
    dot = tree.to_dot()

    expected = "\n".join(
        [
            "digraph LogicTree {",
            "  rankdir=TB;",
            '  "n0" [label="ROOT" style="filled" fillcolor="#111827"];',
            '  "n1" [label="CLAUSE: A person" style="filled" fillcolor="#2563eb"];',
            '  "n0" -> "n1" [label="SEQUENCE" constraint=false style="dotted" color="#9ca3af"];',
            "}",
        ]
    )
    assert dot == expected


def test_sqlite_projection_preserves_ord() -> None:
    tokens = [
        Token(text="A", lemma="a", pos="DET", dep="", ent_type=""),
        Token(text="person", lemma="person", pos="NOUN", dep="", ent_type=""),
        Token(text="must", lemma="must", pos="AUX", dep="", ent_type=""),
    ]
    tree = build(tokens, source_id="doc-proj")
    conn = sqlite3.connect(":memory:")

    project_logic_tree_to_sqlite(tree, conn, doc_id="doc-proj")

    cursor = conn.execute(
        "SELECT parent_id, child_id, ord FROM logic_edges WHERE doc_id = ? ORDER BY parent_id, ord",
        ("doc-proj",),
    )
    rows = cursor.fetchall()
    expected = []
    for parent_id in {edge.parent_id for edge in tree.edges}:
        for idx, edge in enumerate(tree.children_of(parent_id)):
            expected.append((parent_id, edge.child_id, idx))
    expected.sort()
    rows_sorted = sorted(rows)
    assert rows_sorted == expected

    cursor = conn.execute(
        "SELECT node_id, node_type, span_i, span_j FROM logic_nodes WHERE doc_id = ? ORDER BY node_id",
        ("doc-proj",),
    )
    node_rows = cursor.fetchall()
    assert any(row[1] == NodeType.ROOT.value for row in node_rows)


def test_pipeline_build_and_persist_logic_tree(tmp_path) -> None:
    text = "A person must comply with notice."
    tree = pipeline.build_and_persist_logic_tree(
        text,
        source_id="doc-persist",
        artifacts_dir=tmp_path,
        sqlite_path=tmp_path / "logic_tree.sqlite",
    )

    output = tmp_path / "doc-persist.logic_tree.json"
    assert output.exists()
    with output.open(encoding="utf-8") as fp:
        persisted = fp.read().strip()
    assert persisted
    assert tree.to_dict()["version"] == "logic-tree-v1"


def test_sqlite_roundtrip_parity() -> None:
    tokens = [
        Token(text="A", lemma="a", pos="DET", dep="", ent_type=""),
        Token(text="person", lemma="person", pos="NOUN", dep="", ent_type=""),
        Token(text="must", lemma="must", pos="AUX", dep="", ent_type=""),
        Token(text="not", lemma="not", pos="PART", dep="", ent_type=""),
        Token(text="enter", lemma="enter", pos="VERB", dep="", ent_type=""),
        Token(text="the", lemma="the", pos="DET", dep="", ent_type=""),
        Token(text="premises", lemma="premises", pos="NOUN", dep="", ent_type=""),
    ]

    tree = build(tokens, source_id="doc-roundtrip")
    conn = sqlite3.connect(":memory:")
    prepare_logic_tree_schema(conn)
    project_logic_tree_to_sqlite(tree, conn, doc_id="doc-roundtrip")

    restored = rehydrate_logic_tree_from_sqlite(conn, doc_id="doc-roundtrip")

    assert tree.root_id == restored.root_id
    original_nodes = {node.id: node for node in tree.nodes}
    restored_nodes = {node.id: node for node in restored.nodes}
    assert original_nodes.keys() == restored_nodes.keys()

    for node_id, node in original_nodes.items():
        other = restored_nodes[node_id]
        assert node.node_type == other.node_type
        assert node.span == other.span
        assert node.source_id == other.source_id

    original_post = [n.id for n in walk_postorder(tree)]
    restored_post = [n.id for n in walk_postorder(restored)]
    assert original_post == restored_post


def test_fts_search_resolves_nodes() -> None:
    tokens = [
        Token(text="A", lemma="a", pos="DET", dep="", ent_type=""),
        Token(text="person", lemma="person", pos="NOUN", dep="", ent_type=""),
        Token(text="must", lemma="must", pos="AUX", dep="", ent_type=""),
        Token(text="not", lemma="not", pos="PART", dep="", ent_type=""),
        Token(text="enter", lemma="enter", pos="VERB", dep="ROOT", ent_type=""),
    ]
    tree = build(tokens, source_id="doc-fts")
    conn = sqlite3.connect(":memory:")
    prepare_logic_tree_schema(conn)
    project_logic_tree_to_sqlite(tree, conn, doc_id="doc-fts")
    index_tokens_for_fts(conn, doc_id="doc-fts", tokens=tokens)

    results = search_fts_over_logic_tree(conn, "must")
    assert results
    result = results[0]
    assert result["doc_id"] == "doc-fts"
    assert any("must" in snippet for snippet in result["snippets"])
    # modal node should be included because its span covers the hit
    modal_nodes = [node.id for node in tree.nodes if node.node_type is NodeType.MODAL]
    for node_id in modal_nodes:
        assert node_id in result["node_ids"]
