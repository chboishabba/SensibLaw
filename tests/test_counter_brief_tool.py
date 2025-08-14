import json
import os
import subprocess
from pathlib import Path


def test_counter_brief_cli(tmp_path: Path):
    brief = tmp_path / "brief.txt"
    brief.write_text("First claim.\nSecond claim.\n")

    cmd = [
        "python",
        "-m",
        "src.cli",
        "tools",
        "counter-brief",
        "--file",
        str(brief),
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{Path.cwd()}:{env.get('PYTHONPATH', '')}"
    completed = subprocess.run(
        cmd, capture_output=True, text=True, check=True, cwd=tmp_path, env=env
    )

    data = json.loads(completed.stdout)
    assert len(data["rebuttals"]) == 2
    out_path = tmp_path / "output" / "counter_briefs" / "brief.json"
    assert out_path.exists()
    file_data = json.loads(out_path.read_text())
    assert file_data == data
