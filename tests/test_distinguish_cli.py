import json
import subprocess
from pathlib import Path


def test_cli_distinguish(tmp_path: Path):
    base = ["base fact", "Held: yes"]
    candidate = ["other fact", "Held: yes"]
    base_file = tmp_path / "base.json"
    cand_file = tmp_path / "cand.json"
    base_file.write_text(json.dumps(base))
    cand_file.write_text(json.dumps(candidate))

    cmd = [
        "python",
        "-m",
        "src.cli",
        "distinguish",
        "--base",
        str(base_file),
        "--candidate",
        str(cand_file),
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(completed.stdout)
    texts = [o["text"] for o in data["overlaps"]]
    assert "Held: yes" in texts
    missing = [m["text"] for m in data["missing"]]
    assert "base fact" in missing
