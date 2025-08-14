import subprocess
from pathlib import Path


def test_repro_adversarial_creates_bundle(tmp_path: Path):
    out_dir = tmp_path / "bundle"
    cmd = [
        "python",
        "-m",
        "src.cli",
        "repro",
        "adversarial",
        "--topic",
        "demo",
        "--output",
        str(out_dir),
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True)
    assert completed.returncode == 0
    assert (out_dir / "demo.html").exists()
    assert (out_dir / "demo.pdf").exists()
