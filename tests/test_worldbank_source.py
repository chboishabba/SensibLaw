from __future__ import annotations

import requests

from src.sources.worldbank_adapter import fetch_live_worldbank_report, mock_worldbank_bundle


class FakeHeadResponse:
    def __init__(self, status=200):
        self._status = status

    def raise_for_status(self) -> None:
        if self._status >= 400:
            raise requests.RequestException("boom")


def test_mock_worldbank_bundle() -> None:
    bundle = mock_worldbank_bundle()
    assert bundle
    assert bundle[0]["source_family"] == "worldbank"


def test_fetch_live_worldbank_report(monkeypatch) -> None:
    def stub_head(*args, **kwargs):
        return FakeHeadResponse()

    monkeypatch.setattr("src.sources.worldbank_adapter.requests.head", stub_head)
    normalized = fetch_live_worldbank_report(
        doc_id="WDR2021",
        url="https://documents.worldbank.org/en/publication/documents-reports/documentdetail/401781609909355252/world-development-report-2021",
    )
    assert normalized is not None
    assert normalized["source_type"] == "report"
