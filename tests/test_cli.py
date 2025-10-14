import json
import subprocess
from datetime import date, datetime
from pathlib import Path

from src.models.document import Document, DocumentMetadata
from src.models.provision import Atom, Provision
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
        canonical_id="cli-123",
    )
    provision_v1 = Provision(
        text="CLI provision",
        identifier="clause 1",
        atoms=[Atom(type="duty", text="Preserve CLI atoms")],
    )
    provision_v2 = Provision(
        text="CLI provision",
        identifier="clause 1 rev2",
        atoms=[Atom(type="duty", text="Preserve CLI atoms")],
    )
    store.add_revision(
        doc_id, Document(meta, "old", provisions=[provision_v1]), date(2020, 1, 1)
    )
    store.add_revision(
        doc_id, Document(meta, "new", provisions=[provision_v2]), date(2021, 1, 1)
    )
    store.close()
    return str(db), doc_id


def run_cli(db_path: str, *args: str) -> str:
    cmd = ["python", "-m", "cli", "get", "--db", db_path, *args]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return completed.stdout.strip()


def run_tests_cli(*args: str) -> str:
    cmd = ["python", "-m", "src.cli", "tests", "run", *args]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return completed.stdout.strip()


def test_cli_as_at(tmp_path: Path):
    db_path, doc_id = setup_db(tmp_path)
    out = run_cli(db_path, "--id", str(doc_id), "--as-at", "2020-06-01")
    data = json.loads(out)
    assert data["body"] == "old"
    assert data["metadata"]["source_url"] == "http://example.com"
    assert data["metadata"]["checksum"] == "xyz"
    assert data["provisions"][0]["atoms"][0]["text"] == "Preserve CLI atoms"
    out2 = run_cli(db_path, "--id", str(doc_id), "--as-at", "2021-06-01")
    data2 = json.loads(out2)
    assert data2["body"] == "new"
    assert data2["provisions"][0]["atoms"][0]["text"] == "Preserve CLI atoms"


def test_tests_run(tmp_path: Path):
    story = {
        "delay": True,
        "abuse_of_process": False,
        "fair_trial_possible": False,
    }
    story_path = tmp_path / "story.json"
    story_path.write_text(json.dumps(story))

    out = run_tests_cli(
        "--ids",
        "glj:permanent_stay",
        "--story",
        str(story_path),
    )

    data = json.loads(out)
    result = data["results"]["glj:permanent_stay"]
    assert result["name"] == "GLJ Permanent Stay"
    assert result["passed"] is False
    assert result["factors"] == {
        "delay": True,
        "abuse_of_process": False,
        "fair_trial_possible": False,
    }
def test_query_treatment_cli():
    cmd = [
        "python",
        "-m",
        "src.cli",
        "cases",
        "treatment",
        "--case-id",
        "case123",
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
    result = json.loads(completed.stdout)
    assert result["case_id"] == "case123"
    citations = [t["neutral_citation"] for t in result["authorities"]]
    assert citations[:2] == ["[2015] HCA 10", "[2016] FamCAFC 50"]
    assert "what_to_cite_next" in result
