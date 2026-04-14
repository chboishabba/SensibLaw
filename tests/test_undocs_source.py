from __future__ import annotations

import requests

from src.sources.undocs import fetch_live_undoc, mock_undoc_bundle, normalized_undoc_symbol


class DummyResponse:
    def __init__(self, text: str, status_code: int = 200, url: str = "https://undocs.org") -> None:
        self.text = text
        self.status_code = status_code
        self.url = url

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.RequestException("boom")


def test_mock_undoc_bundle_normalizes_source_unit() -> None:
    bundle = mock_undoc_bundle()
    assert bundle
    assert bundle[0]["source_family"] == "undocs"
    assert bundle[0]["primary_language"] == "en"
    assert bundle[0]["translation_status"] == "original"


def test_fetch_live_undoc_fallback(monkeypatch) -> None:
    class BrokenResponse:
        def raise_for_status(self) -> None:
            raise requests.RequestException("fail")

    def fail_get(*args, **kwargs):
        raise requests.RequestException("down")

    monkeypatch.setattr("src.sources.undocs.requests.get", fail_get)
    normalized = normalized_undoc_symbol()
    assert normalized["source_family"] == "undocs"


def test_fetch_live_undoc_success(monkeypatch) -> None:
    def success_get(url, *args, **kwargs):
        if url == "https://undocs.org/INFCIRC/12/Rev.1":
            return DummyResponse(
                "<a href='/en/INFCIRC/12/Rev.1' role='button' lang='en'>English</a><title>Select a language</title>",
                url=url,
            )
        return DummyResponse(
            "<html><title>Document Viewer</title><iframe src='https://documents.un.org/api/symbol/access?s=INFCIRC/12/Rev.1&amp;l=en&amp;t=pdf'></iframe></html>",
            url="https://docs.un.org/en/INFCIRC/12/Rev.1",
        )

    def success_head(url, *args, **kwargs):
        return DummyResponse("", url=url)

    monkeypatch.setattr("src.sources.undocs.requests.get", success_get)
    monkeypatch.setattr("src.sources.undocs.requests.head", success_head)
    normalized = normalized_undoc_symbol(language="en")
    assert normalized["title"] == "UN document INFCIRC/12/Rev.1"
    assert normalized["url"] == "https://documents.un.org/api/symbol/access?s=INFCIRC/12/Rev.1&l=en&t=pdf"
