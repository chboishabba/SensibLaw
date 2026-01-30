from types import SimpleNamespace
from pathlib import Path

from src.sources.base import FetchResult
from src.ingestion.austlii_pipeline import ingest_pdf_from_search


class FakeSearchAdapter:
    def __init__(self, html: str):
        self.html = html
        self.last_query = None

    def search(self, q):
        self.last_query = q
        return self.html


class FakeFetchAdapter:
    def __init__(self):
        self.calls = 0
        self.last_url = None

    def fetch(self, url: str) -> FetchResult:
        self.calls += 1
        self.last_url = url
        return FetchResult(
            content=b"%PDF-1.4 fake",
            content_type="application/pdf",
            url=url,
            metadata={"source": "austlii"},
        )


def test_pipeline_orchestrates_search_fetch_and_ingest(monkeypatch, tmp_path):
    html = Path("tests/fixtures/austlii/sino_results_sample.html").read_text(encoding="utf-8")
    search_adapter = FakeSearchAdapter(html)
    fetch_adapter = FakeFetchAdapter()

    captured = {}

    def fake_process(pdf_path, db_path=None, **kwargs):
        captured["pdf_path"] = Path(pdf_path)
        captured["db_path"] = db_path
        return "doc", 1

    monkeypatch.setattr("src.ingestion.austlii_pipeline.process_pdf", fake_process)

    doc, stored = ingest_pdf_from_search(
        query="mabo",
        vc="/au",
        db_path=tmp_path / "store.db",
        search_adapter=search_adapter,
        fetch_adapter=fetch_adapter,
    )

    assert doc == "doc"
    assert stored == 1
    assert fetch_adapter.calls == 1
    assert captured["db_path"] == tmp_path / "store.db"
    assert captured["pdf_path"].exists()


def test_hit_selection_by_index(monkeypatch, tmp_path):
    html = Path("tests/fixtures/austlii/sino_results_sample.html").read_text(encoding="utf-8")
    search_adapter = FakeSearchAdapter(html)
    fetch_adapter = FakeFetchAdapter()

    def fake_process(pdf_path, db_path=None, **kwargs):
        return "doc", 1

    monkeypatch.setattr("src.ingestion.austlii_pipeline.process_pdf", fake_process)

    doc, stored = ingest_pdf_from_search(
        query="mabo",
        vc="/au",
        db_path=tmp_path / "store.db",
        search_adapter=search_adapter,
        fetch_adapter=fetch_adapter,
        strategy="by_index",
        index=1,
    )
    assert fetch_adapter.last_url.endswith("/2003/2.html")
    assert stored == 1
