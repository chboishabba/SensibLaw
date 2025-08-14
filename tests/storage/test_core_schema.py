import sqlite3

from src.storage.core import Storage


def test_schema_and_crud(tmp_path):
    db_path = tmp_path / "test.db"
    store = Storage(db_path)

    conn = sqlite3.connect(db_path)
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"nodes", "edges", "frames", "action_templates", "corrections", "glossary", "receipts"} <= tables

    node_id = store.insert_node("entity", {"a": 1})
    node = store.get_node(node_id)
    assert node is not None and node.type == "entity" and node.data["a"] == 1

    edge_id = store.insert_edge(node_id, node_id, "rel", {"weight": 5})
    edge = store.get_edge(edge_id)
    assert edge is not None and edge.source == node_id and edge.data["weight"] == 5

    frame_id = store.insert_frame(node_id, {"frame": "info"})
    frame = store.get_frame(frame_id)
    assert frame is not None and frame.node_id == node_id and frame.data["frame"] == "info"

    action_id = store.insert_action_template("greet", {"text": "hi"})
    action = store.get_action_template(action_id)
    assert action is not None and action.name == "greet"

    corr_id = store.insert_correction(node_id, "fix", {"x": 2})
    correction = store.get_correction(corr_id)
    assert correction is not None and correction.suggestion == "fix"

    gloss_id = store.insert_glossary_entry("term", "definition")
    gloss = store.get_glossary_entry(gloss_id)
    assert gloss is not None and gloss.term == "term"

    rec_id = store.insert_receipt({"status": "ok"})
    receipt = store.get_receipt(rec_id)
    assert receipt is not None and receipt.data["status"] == "ok"

    store.close()
