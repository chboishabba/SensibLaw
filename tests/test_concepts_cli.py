import json
import subprocess
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))


def run_cli(text: str) -> str:
    cmd = ["python", "-m", "src.cli", "concepts", "match", text]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return completed.stdout.strip()


def test_concepts_match_cli():
    out = run_cli("permanent stay")
    data = json.loads(out)
    assert any(hit["concept_id"] == "stay_permanent" for hit in data)
