"""Tests for the Brexit National Archives lane helpers."""

from typing import Mapping

from SensibLaw.src.sources.national_archives.brexit_national_archives_lane import (
    build_brexit_national_archives_manifest,
    fetch_brexit_archive_records,
    normalized_archive_records,
)


def test_manifest_contains_expected_fields() -> None:
    manifest = build_brexit_national_archives_manifest()
    assert manifest["lane_id"].startswith("brexit_national_archives")
    assert "search_constraints" in manifest
    assert manifest["policy_role"].startswith("derived-only")
    targets = manifest.get("targets") or []
    assert len(targets) == 2
    for target in targets:
        assert target["collection"].startswith("UK National Archives")
        assert target["url"].startswith("https://discovery.nationalarchives.gov.uk")


def test_normalized_records_schema() -> None:
    records = normalized_archive_records()
    assert len(records) == 2
    for record in records:
        assert record["schema_version"].startswith("brexit.national_archives.record")
        assert record["search_focus"] == "BREXIT-INTENT"
        assert "lane" in record["provenance"]


class _StubResponse:
    def __init__(self, url: str, text: str) -> None:
        self.url = url
        self._text = text

    def raise_for_status(self) -> None:
        return

    @property
    def text(self) -> str:
        return self._text


def test_fetch_records_uses_live_response(monkeypatch) -> None:
    def fake_get(url: str, timeout: int, headers: Mapping[str, str]) -> _StubResponse:
        return _StubResponse(url + "?live=1", "Live archive text sample.")

    monkeypatch.setattr("SensibLaw.src.sources.national_archives.brexit_national_archives_lane.requests.get", fake_get)
    records = fetch_brexit_archive_records()
    assert records[0]["document_text"] == "Live archive text sample."
    assert "?live=1" in records[0]["url"]


def test_fetch_records_falls_back_to_fixture(monkeypatch) -> None:
    def fake_get(_url: str, **_kwargs):
        raise RuntimeError("dialing blocked")

    monkeypatch.setattr("SensibLaw.src.sources.national_archives.brexit_national_archives_lane.requests.get", fake_get)
    records = fetch_brexit_archive_records()
    assert records[0]["text_excerpt"].startswith("The Cabinet resolved")
    assert records[0]["provenance"].get("fixture")
