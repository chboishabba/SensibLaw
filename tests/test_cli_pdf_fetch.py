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
        "def extract_text(path):\n"
        "    return '1 Heading One\\nAgents must file reports.\\f2 Heading Two\\nDirectors may refuse permits.'\n"
    )

    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")
    out_path = tmp_path / "out.json"
    db_path = tmp_path / "store.db"

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
        "--db",
        str(db_path),
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=True, env=env)
    payload = json.loads(completed.stdout)
    assert "document" in payload
    assert payload.get("doc_id") is not None
    document = payload["document"]
    assert document["metadata"]["jurisdiction"] == "US"
    provisions = document["provisions"]
    assert [prov["identifier"] for prov in provisions] == ["1", "2"]
    assert [prov["heading"] for prov in provisions] == ["Heading One", "Heading Two"]
    for provision in provisions:
        assert provision["principles"], "expected non-empty principles from CLI output"
        assert provision["atoms"], "expected non-empty atoms from CLI output"

    assert out_path.exists()
    saved = json.loads(out_path.read_text())
    assert saved["metadata"]["citation"] == "CIT"
    saved_provisions = saved["provisions"]
    assert [prov["identifier"] for prov in saved_provisions] == ["1", "2"]
    assert [prov["heading"] for prov in saved_provisions] == [
        "Heading One",
        "Heading Two",
    ]
    for provision in saved_provisions:
        assert provision["principles"], "expected principles persisted to disk"
        assert provision["atoms"], "expected atoms persisted to disk"

    get_cmd = [
        "python",
        "-m",
        "cli",
        "get",
        "--db",
        str(db_path),
        "--id",
        str(payload["doc_id"]),
    ]
    got = subprocess.run(get_cmd, capture_output=True, text=True, check=True, env=env)
    retrieved = json.loads(got.stdout)
    assert retrieved["provisions"], "expected provisions from stored document"
    for provision in retrieved["provisions"]:
        assert provision["atoms"], "expected atoms persisted in database"
