import json
import subprocess
from pathlib import Path


def test_cli_distinguish():
    story_path = Path("tests/fixtures/glj_permanent_stay_story.json")
    cmd = [
        "python",
        "-m",
        "cli",
        "distinguish",
        "--case",
        "glj",
        "--story",
        str(story_path),
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(completed.stdout)
    assert "overlaps" in data
    missing_ids = {m["id"] for m in data["missing"]}
    assert "delay" in missing_ids
