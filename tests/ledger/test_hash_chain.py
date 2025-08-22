import hashlib
import sqlite3
import xml.etree.ElementTree as ET

import pytest


def test_hash_chain(tmp_path, monkeypatch):
    db_path = tmp_path / "corr.db"
    feed_path = tmp_path / "feed.atom"
    monkeypatch.setenv("LEDGER_DB", str(db_path))
    monkeypatch.setenv("LEDGER_FEED", str(feed_path))

    from src.ledger import append_correction
    from src.ledger.feed import build_feed, verify_feed

    h1 = append_correction("n1", "a", "b", "r1", "alice", "")
    h2 = append_correction("n1", "b", "c", "r2", "bob", h1)
    h3 = append_correction("n1", "c", "d", "r3", "carl", h2)

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT node_id, before_hash, after_hash, reason, reporter, prev_hash, this_hash FROM corrections ORDER BY rowid"
        ).fetchall()

    assert rows[1]["prev_hash"] == h1
    assert rows[1]["this_hash"] == h2
    assert rows[2]["prev_hash"] == h2
    assert rows[2]["this_hash"] == h3

    for row in rows:
        body = "|".join(
            [
                row["node_id"],
                row["before_hash"],
                row["after_hash"],
                row["reason"],
                row["reporter"],
                row["prev_hash"] or "",
            ]
        )
        recomputed = hashlib.sha256(body.encode("utf-8")).hexdigest()
        assert recomputed == row["this_hash"]

    build_feed()

    tree = ET.parse(feed_path)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    prev_id = None
    for entry in tree.findall("atom:entry", ns):
        entry_id = entry.findtext("atom:id", namespaces=ns)
        content = entry.findtext("atom:content", namespaces=ns) or ""
        prev_hash = content.split("|")[-1]
        if prev_id:
            assert prev_hash == prev_id
        prev_id = entry_id

    verify_feed()

    root = tree.getroot()
    entries = root.findall("atom:entry", ns)
    bad_content = entries[1].find("atom:content", ns)
    parts = bad_content.text.split("|")
    parts[-1] = "corrupted"
    bad_content.text = "|".join(parts)
    feed_path.write_bytes(ET.tostring(root, encoding="utf-8", xml_declaration=True))

    with pytest.raises(ValueError):
        verify_feed()
