import json
from types import SimpleNamespace
from pathlib import Path
import sys

import pytest

sys.path.append(str(Path(__file__).resolve().parents[2]))
from src import austlii_client


@pytest.fixture
def setup_client(tmp_path, monkeypatch):
    monkeypatch.setattr(austlii_client, "BASE_DATA_DIR", tmp_path)
    monkeypatch.setattr(austlii_client, "JUDGMENT_DIR", tmp_path / "judgments")
    monkeypatch.setattr(austlii_client, "LEGISLATION_DIR", tmp_path / "legislation")
    austlii_client.JUDGMENT_DIR.mkdir()
    austlii_client.LEGISLATION_DIR.mkdir()
    return austlii_client.AustLIIClient()


def test_parse_judgment(setup_client, tmp_path, monkeypatch):
    client = setup_client
    html = """
    <html><body>
    <h1>Sample Judgment</h1>
    <span class='date'>2020-01-01</span>
    <p>1 First point</p>
    <p>1.1 Sub point</p>
    <p>2 Second point</p>
    </body></html>
    """
    monkeypatch.setattr(client, "_get", lambda url: SimpleNamespace(content=html.encode("utf-8")))
    doc = client.fetch_judgment("http://example.com/judgment")
    assert doc.metadata.canonical_id == "sample-judgment"
    assert doc.metadata.provenance == "http://example.com/judgment"
    assert len(doc.provisions) == 2
    assert doc.provisions[0].identifier == "1"
    assert doc.provisions[0].children[0].identifier == "1.1"
    path = austlii_client.JUDGMENT_DIR / "sample-judgment.json"
    data = json.loads(path.read_text())
    assert data["provisions"][0]["identifier"] == "1"
    assert data["provisions"][0]["children"][0]["identifier"] == "1.1"


def test_parse_legislation(setup_client, tmp_path, monkeypatch):
    client = setup_client
    html = """
    <html><body>
    <h1>Sample Act 2020</h1>
    <span class='date'>2020-06-30</span>
    <div>1 Section one</div>
    <div>1.1 Subsection</div>
    <div>2 Section two</div>
    </body></html>
    """
    monkeypatch.setattr(client, "_get", lambda url: SimpleNamespace(content=html.encode("utf-8")))
    doc = client.fetch_legislation("http://example.com/act")
    assert doc.metadata.canonical_id == "sample-act-2020"
    assert len(doc.provisions) == 2
    assert doc.provisions[0].identifier == "1"
    assert doc.provisions[0].children[0].identifier == "1.1"
    path = austlii_client.LEGISLATION_DIR / "sample-act-2020.json"
    data = json.loads(path.read_text())
    assert data["provisions"][0]["children"][0]["identifier"] == "1.1"
