from pathlib import Path
import sqlite3

from src.ontology.lookup import batch_lookup


def test_batch_lookup_logs_results(tmp_path: Path) -> None:
    db_path = tmp_path / "store.db"
    terms = ["with intent to cause death", "unknown term"]

    results = batch_lookup(terms, db_path=db_path)

    assert len(results) == 2
    assert results[0].label is not None
    assert results[0].description

    connection = sqlite3.connect(db_path)
    try:
        rows = connection.execute(
            "SELECT term, provider, label, description, confidence, looked_up_at"
            " FROM ontology_lookup_log ORDER BY id"
        ).fetchall()
    finally:
        connection.close()

    assert [row[0] for row in rows] == terms
    assert rows[0][1] == "glossary"
    assert rows[0][2]
    assert rows[0][3]
    assert rows[0][5] is not None
