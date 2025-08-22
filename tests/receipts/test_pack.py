import hashlib
import subprocess
from pathlib import Path


def build_pack(dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    data_file = dest / "data.txt"
    data_file.write_text("hello world\n")
    digest = hashlib.sha256(data_file.read_bytes()).hexdigest()
    sums = dest / "SHA256SUMS"
    sums.write_text(f"{digest}  {data_file.name}\n")
    verify = dest / "verify.sh"
    verify.write_text("#!/bin/sh\nsha256sum -c SHA256SUMS\n")
    verify.chmod(0o755)
    return verify


def run_verify(verify: Path, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run([str(verify)], cwd=cwd, capture_output=True)


def test_verify_succeeds(tmp_path: Path):
    verify = build_pack(tmp_path)
    completed = run_verify(verify, tmp_path)
    assert completed.returncode == 0


def test_verify_fails_on_modification(tmp_path: Path):
    verify = build_pack(tmp_path)
    (tmp_path / "data.txt").write_text("tampered\n")
    completed = run_verify(verify, tmp_path)
    assert completed.returncode != 0
