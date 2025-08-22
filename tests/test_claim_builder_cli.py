import subprocess
from pathlib import Path


def test_claim_builder_creates_yaml(tmp_path: Path):
    cmd = ["python", "-m", "src.cli", "tools", "claim-builder", "--dir", str(tmp_path)]
    user_input = "Alice\nBob\nWidget issue\n100\nrcpt-1,rcpt-2\n"
    result = subprocess.run(cmd, input=user_input, text=True, capture_output=True, check=True)
    files = list(tmp_path.glob("*.yaml"))
    assert len(files) == 1
    content = files[0].read_text()
    assert "claimant: Alice" in content
    assert "respondent: Bob" in content
    assert "- rcpt-1" in content
    assert result.returncode == 0
