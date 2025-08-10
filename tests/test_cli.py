import json
import subprocess
from pathlib import Path


def make_sample_data(tmp_path: Path) -> Path:
    data = [
        {
            "citation": "123 U.S. 456",
            "title": "Example v. Sample",
            "content": "This case discusses examples and samples.",
        },
        {
            "citation": "789 U.S. 101",
            "title": "Another v. Case",
            "content": "Another case with different facts.",
        },
    ]
    path = tmp_path / "data.json"
    path.write_text(json.dumps(data))
    return path


def run_cli(path: Path, *args: str) -> str:
    cmd = ["python", "-m", "src.cli", str(path), *args]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return completed.stdout


def test_search(tmp_path: Path):
    data_path = make_sample_data(tmp_path)
    out = run_cli(data_path, "--search", "examples")
    assert "Example v. Sample" in out
    assert "Another v. Case" not in out


def test_select_by_citation(tmp_path: Path):
    data_path = make_sample_data(tmp_path)
    out = run_cli(data_path, "--citation", "789 U.S. 101")
    assert "Another v. Case" in out
    assert "Example v. Sample" not in out


def test_select_by_title(tmp_path: Path):
    data_path = make_sample_data(tmp_path)
    out = run_cli(data_path, "--title", "Example v. Sample")
    assert "123 U.S. 456" in out
    assert "Another v. Case" not in out
