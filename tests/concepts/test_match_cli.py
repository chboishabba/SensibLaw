import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATTERNS = ROOT / "data/concepts/triggers.au.json"


def run_cli(text: str) -> list[dict]:
    cmd = [
        "python",
        "-m",
        "src.cli",
        "concepts",
        "match",
        "--patterns-file",
        str(PATTERNS),
        "--text",
        text,
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(completed.stdout)


def test_match_cli_deterministic():
    text = "The doctrine of terra nullius was overturned; no permanent stay followed."
    out1 = run_cli(text)
    out2 = run_cli(text)
    assert out1 == out2
    ids = [n["id"] for n in out1]
    assert ids == ["Concept#terra_nullius", "Concept#permanent_stay"]
    starts = [n["start"] for n in out1]
    assert starts == sorted(starts)
