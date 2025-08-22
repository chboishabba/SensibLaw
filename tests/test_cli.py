import json
import subprocess
from datetime import date, datetime
from pathlib import Path

from src.models.document import Document, DocumentMetadata
from src.storage import VersionedStore


def setup_db(tmp_path: Path) -> tuple[str, int]:
    db = tmp_path / "store.db"
    store = VersionedStore(str(db))
    doc_id = store.generate_id()
    meta = DocumentMetadata(
        jurisdiction="US",
        citation="CIT",
        date=date(2020, 1, 1),
        source_url="http://example.com",
        retrieved_at=datetime(2020, 1, 2, 0, 0, 0),
        checksum="xyz",
        licence="CC0",
    )
    store.add_revision(doc_id, Document(meta, "old"), date(2020, 1, 1))
    store.add_revision(doc_id, Document(meta, "new"), date(2021, 1, 1))
    store.close()
    return str(db), doc_id


def run_cli(db_path: str, *args: str) -> str:
    cmd = ["python", "-m", "cli", "get", "--db", db_path, *args]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return completed.stdout.strip()


def test_cli_as_at(tmp_path: Path):
    db_path, doc_id = setup_db(tmp_path)
    out = run_cli(db_path, "--id", str(doc_id), "--as-at", "2020-06-01")
    data = json.loads(out)
    assert data["body"] == "old"
    assert data["metadata"]["source_url"] == "http://example.com"
    assert data["metadata"]["checksum"] == "xyz"
    out2 = run_cli(db_path, "--id", str(doc_id), "--as-at", "2021-06-01")
    data2 = json.loads(out2)
    assert data2["body"] == "new"
