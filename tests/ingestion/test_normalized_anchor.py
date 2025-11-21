from datetime import date
import sqlite3

from src.ingestion.anchors import NormalizedOntologyStore
from src.models.document import Document, DocumentMetadata
from src.models.provision import RuleAtom


def test_anchor_rule_atoms_to_normalized_tables(tmp_path):
    document = Document(
        metadata=DocumentMetadata(
            jurisdiction="AU", citation="[2023] HCA 1", date=date(2023, 1, 1)
        ),
        body="Sample body",
    )
    rule_atom = RuleAtom(actor="a person", modality="must", action="pay damages", text="A person must pay damages")

    db_path = tmp_path / "ontology.db"
    with NormalizedOntologyStore(db_path) as store:
        results = store.anchor_rule_atoms(document, [rule_atom], category="case")

    assert results[0].legal_source_id == "[2023] HCA 1"
    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM legal_sources").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM actor_classes").fetchone()[0] >= 1
        assert conn.execute("SELECT COUNT(*) FROM rule_actor_classes").fetchone()[0] == len(results[0].actor_classes)
    finally:
        conn.close()
