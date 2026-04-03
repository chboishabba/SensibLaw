from __future__ import annotations

import requests

from src.sources.icj_records import fetch_live_icj_record, mock_icj_bundle


class FakeHeadResponse:
    def __init__(self, status=200):
        self._status = status

    def raise_for_status(self) -> None:
        if self._status >= 400:
            raise requests.RequestException("boom")


def test_mock_icj_bundle() -> None:
    bundle = mock_icj_bundle()
    assert bundle
    assert bundle[0]["jurisdiction"] == "international"


def test_fetch_live_icj_record(monkeypatch) -> None:
    def stub_head(*args, **kwargs):
        return FakeHeadResponse()

    monkeypatch.setattr("src.sources.icj_records.requests.head", stub_head)
    normalized = fetch_live_icj_record(
        record_id="170-20201112-ADV-01-00-EN",
        url="https://www.icj-cij.org/sites/default/files/case-related/170/170-20201112-ADV-01-00-EN.pdf",
    )
    assert normalized and normalized["source_family"] == "icj_cases"
