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
    texts = [o["text"] for o in data["overlaps"]]
    assert "Held: yes" in texts
    missing = [m["text"] for m in data["missing"]]
    assert "base fact" in missing


def test_distinguish_cli_case_story():
    cmd = [
        "python",
        "-m",
        "src.cli",
        "distinguish",
        "--case",
        "[2002] HCA 14",
        "--story",
        "tests/fixtures/glj_permanent_stay_story.json",
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(completed.stdout)
    assert "overlap" in data and "diffs" in data
    overlap = {o["cue"]: o["paragraphs"] for o in data["overlap"]}
    diffs = {d["cue"]: d["paragraphs"] for d in data["diffs"]}
    assert overlap.get("delay") == [1]
    assert diffs.get("lost evidence") == [2]


def test_distinguish_cli_missing_case():
    cmd = [
        "python",
        "-m",
        "src.cli",
        "distinguish",
        "--story",
        "tests/fixtures/glj_permanent_stay_story.json",
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True)
    assert completed.returncode != 0
    assert "case" in completed.stderr.lower()


def test_distinguish_cli_bad_story():
    cmd = [
        "python",
        "-m",
        "src.cli",
        "distinguish",
        "--case",
        "[2002] HCA 14",
        "--story",
        "tests/fixtures/missing_story.json",
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True)
    assert completed.returncode != 0
    assert "error" in completed.stderr.lower()

    assert "overlaps" in data
    missing_ids = {m["id"] for m in data["missing"]}
    assert "delay" in missing_ids
