import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))

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
    assert receipt.simhash and receipt.minhash

    store.close()


def test_duplicate_node_ids_raise_integrity_error(tmp_path):
    db_path = tmp_path / "test.db"
    store = Storage(db_path)
    cur = store.conn.cursor()
    cur.execute("INSERT INTO nodes(id, type, data) VALUES (1, 'entity', '{}')")
    store.conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        cur.execute("INSERT INTO nodes(id, type, data) VALUES (1, 'entity', '{}')")
    store.close()


def test_malformed_json_in_props_raises_value_error(tmp_path):
    db_path = tmp_path / "test.db"
    store = Storage(db_path)
    store.conn.execute(
        "INSERT INTO nodes(id, type, data) VALUES (1, 'entity', '{bad json}')"
    )
    store.conn.commit()
    with pytest.raises(ValueError):
        store.get_node(1)
    store.close()


def test_correction_deletion_rejected(tmp_path):
    db_path = tmp_path / "test.db"
    store = Storage(db_path)
    node_id = store.insert_node("entity", {})
    corr_id = store.insert_correction(node_id, "fix", {})
    with pytest.raises(sqlite3.IntegrityError):
        store.delete_correction(corr_id)
    assert store.get_correction(corr_id) is not None
    store.close()


def test_receipt_indexes_and_duplicate_simhash_rejected(tmp_path):
    db_path = tmp_path / "test.db"
    store = Storage(db_path)
    try:
        store.insert_receipt({"text": "same"})
        with pytest.raises(sqlite3.IntegrityError):
            store.insert_receipt({"text": "same"})
    finally:
        store.close()

    conn = sqlite3.connect(db_path)
    try:
        index_details = {
            row[1]: row[2]
            for row in conn.execute("PRAGMA index_list('receipts')").fetchall()
        }
        assert index_details.get("idx_receipts_minhash") == 0
        assert index_details.get("idx_receipts_simhash") == 1
    finally:
        conn.close()
