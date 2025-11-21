from datetime import date
import sqlite3

from src.ingestion.backfill import backfill_documents
from src.models.document import Document, DocumentMetadata
from src.models.provision import Provision, RuleAtom


def test_backfill_documents_migrates_rule_atoms(tmp_path):
    document = Document(
        metadata=DocumentMetadata(
            jurisdiction="NZ",
            citation="[2022] NZHC 10",
            date=date(2022, 5, 1),
            title="Example",
        ),
        body="",
    )
    provision = Provision(text="sample provision")
    provision.rule_atoms = [RuleAtom(actor="defendant", action="compensate", text="The defendant must compensate")]
    document.provisions.append(provision)

    db_path = tmp_path / "backfill.db"
    summary = backfill_documents([document], db_path=db_path, default_category="case")

    assert summary.rules_migrated == 1
    assert summary.legal_sources_created == 1

    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM rule_atoms").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM legal_sources").fetchone()[0] == 1
    finally:
        conn.close()
