import json
import subprocess
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))


def test_tests_run(tmp_path: Path):
    story = {
        "factors": {
            "f1": {"status": True, "evidence": ["e1"]},
            "f2": {"status": False, "evidence": ["e2"]},
        }
    }
    story_path = tmp_path / "story.json"
    story_path.write_text(json.dumps(story))

    cmd = [
        "python",
        "-m",
        "src.cli",
        "tests",
        "run",
        "--tests",
        "s4AA",
        "--story",
        str(story_path),
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(completed.stdout)

    assert data["concept_id"] == "s4AA"
    results = {r["id"]: r for r in data["results"]}
    assert results["f1"]["status"] == "satisfied"
    assert results["f1"]["evidence"] == ["e1"]
    assert results["f2"]["status"] == "unsatisfied"
    assert results["f2"]["evidence"] == ["e2"]

