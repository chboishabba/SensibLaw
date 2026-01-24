import json
import os
import subprocess
import sys
from pathlib import Path


def test_pdf_fetch_cli(tmp_path):
    # Create stub pdfminer module so pdf_ingest uses predictable text
    stub_pkg = tmp_path / "stubs"
    (stub_pkg / "pdfminer").mkdir(parents=True)
    (stub_pkg / "pdfminer" / "__init__.py").write_text("")
    (stub_pkg / "pdfminer" / "high_level.py").write_text(
        "from types import SimpleNamespace\n\n"
        "def _pages():\n"
        "    text = ('1 Heading One\\nAgents must file reports.\\f2 Heading Two\\n"
        "Directors may refuse permits.')\n"
        "    for page in text.split('\\f'):\n"
        "        yield [SimpleNamespace(get_text=lambda page=page: page)]\n\n"
        "def extract_pages(path):\n"
        "    return _pages()\n\n"
        "def extract_text(path):\n"
        "    return ''.join(page.get_text() + '\\f' for layout in _pages() for page in layout)\n"
    )
    (stub_pkg / "pdfminer" / "layout.py").write_text(
        "class LTAnno: ...\n"
        "class LTChar:\n"
        "    def __init__(self, x0=0, y0=0, x1=0, y1=0, pageid=1, char=None):\n"
        "        self.x0, self.y0, self.x1, self.y1, self.pageid, self.char = x0, y0, x1, y1, pageid, char or ''\n"
        "class LTTextContainer: ...\n"
    )
    (stub_pkg / "pdfminer" / "pdfdocument.py").write_text(
        "class PDFDocument:\n"
        "    def __init__(self, parser):\n"
        "        self.parser = parser\n"
    )
    (stub_pkg / "pdfminer" / "pdfpage.py").write_text(
        "class PDFPage:\n"
        "    @staticmethod\n"
        "    def create_pages(document):\n"
        "        return []\n"
    )
    (stub_pkg / "pdfminer" / "pdfparser.py").write_text(
        "class PDFParser:\n"
        "    def __init__(self, buffer):\n"
        "        self.buffer = buffer\n"
        "    def set_document(self, document):\n"
        "        self.document = document\n"
    )
    (stub_pkg / "pdfminer" / "pdftypes.py").write_text(
        "def resolve1(value):\n"
        "    return value\n"
    )

    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")
    out_path = tmp_path / "out.json"
    db_path = tmp_path / "store.db"
    logic_tree_dir = tmp_path / "logic_tree"
    logic_tree_sqlite = logic_tree_dir / "logic_tree.sqlite"

    env = os.environ.copy()
    env["PYTHONPATH"] = f"{stub_pkg}:{env.get('PYTHONPATH', '')}"
    cmd = [
        sys.executable,
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
        "--title",
        "Provided Title",
        "--db",
        str(db_path),
        "--logic-tree-artifacts",
        str(logic_tree_dir),
        "--logic-tree-sqlite",
        str(logic_tree_sqlite),
        "--logic-tree-source-id",
        "sample-doc",
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=True, env=env)
    payload = json.loads(completed.stdout)
    assert "document" in payload
    assert payload.get("doc_id") is not None
    document = payload["document"]
    assert document["metadata"]["jurisdiction"] == "US"
    assert document["metadata"]["title"] == "Provided Title"
    provisions = document["provisions"]
    assert [prov["identifier"] for prov in provisions] == ["1", "2"]
    assert [prov["heading"] for prov in provisions] == ["Heading One", "Heading Two"]
    for provision in provisions:
        assert provision["principles"], "expected non-empty principles from CLI output"
        assert provision["atoms"], "expected non-empty atoms from CLI output"

    assert out_path.exists()
    saved = json.loads(out_path.read_text())
    assert saved["metadata"]["citation"] == "CIT"
    assert saved["metadata"]["title"] == "Provided Title"
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
        sys.executable,
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

    logic_tree_meta = payload.get("logic_tree")
    assert logic_tree_meta, "expected logic tree metadata in CLI output"
    assert Path(logic_tree_meta["json"]).exists()
    assert Path(logic_tree_meta["sqlite"]).exists()
