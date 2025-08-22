import json
import subprocess
from pathlib import Path


def test_intake_parse_generates_stubs(tmp_path: Path):
    mailbox = Path("tests/fixtures/emails")
    out_dir = tmp_path / "claims"
    cmd = [
        "python",
        "-m",
        "src.cli",
        "intake",
        "parse",
        "--mailbox",
        str(mailbox),
        "--out",
        str(out_dir),
    ]
    subprocess.run(cmd, check=True)

    data1 = json.loads((out_dir / "alice-bob.json").read_text())
    assert data1 == {
        "parties": ["Alice", "Bob"],
        "jurisdiction": "NSW",
        "summary": "Alice alleges Bob breached contract.",
    }
    data2 = json.loads((out_dir / "charlie-delta.json").read_text())
    assert data2 == {
        "parties": ["Charlie", "Delta"],
        "jurisdiction": "VIC",
        "summary": "Land dispute between neighbours.",
    }
