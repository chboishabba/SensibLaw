import hashlib
import sqlite3


def test_hash_chain(tmp_path, monkeypatch):
    db_path = tmp_path / "corr.db"
    monkeypatch.setenv("LEDGER_DB", str(db_path))

    from src.ledger import append_correction

    h1 = append_correction("n1", "a", "b", "r1", "alice", "")
    h2 = append_correction("n1", "b", "c", "r2", "bob", h1)

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT node_id, before_hash, after_hash, reason, reporter, prev_hash, this_hash FROM corrections ORDER BY rowid"
        ).fetchall()

    assert rows[1]["prev_hash"] == h1
    assert rows[1]["this_hash"] == h2

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
