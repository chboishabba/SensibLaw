import json
import os
import subprocess
from pathlib import Path


def test_pdf_fetch_cli(tmp_path):
    # Create stub pdfminer module so pdf_ingest uses predictable text
    stub_pkg = tmp_path / "stubs"
    (stub_pkg / "pdfminer").mkdir(parents=True)
    (stub_pkg / "pdfminer" / "__init__.py").write_text("")
    (stub_pkg / "pdfminer" / "high_level.py").write_text(
        "def extract_text(path):\n    return 'Heading 1\\nHello\\nWorld\\fHeading2\\nSecond Page'\n"
    )

    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")
    out_path = tmp_path / "out.json"

    env = os.environ.copy()
    env["PYTHONPATH"] = f"{stub_pkg}:{env.get('PYTHONPATH', '')}"
    cmd = [
        "python",
        "-m",
        "cli",
        "pdf-fetch",
        str(pdf_path),
        "--output",
        str(out_path),
        "--jurisdiction",
        "US",
        "--citation",
        "CIT",
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=True, env=env)
    data = json.loads(completed.stdout)
    assert data["metadata"]["jurisdiction"] == "US"
    assert out_path.exists()
    saved = json.loads(out_path.read_text())
    assert saved["metadata"]["citation"] == "CIT"
