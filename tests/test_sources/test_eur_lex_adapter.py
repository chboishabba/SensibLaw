from __future__ import annotations

import json

import pytest

import requests

from SensibLaw.src.sources.eur_lex_adapter import EurLexHierarchyAdapter
from SensibLaw.src.sources.eur_lex_adapter import build_celex_url


@pytest.mark.parametrize(
    "citation, expected",
    [
        (
            "CELEX:32018L2001",
            {
                "title": "European Union (Withdrawal) Act 2018",
                "jurisdiction": "United Kingdom",
            },
        ),
        (
            "32020D1144",
            {
                "title": "Treaty on European Union (simplified revision)",
                "jurisdiction": "European Union",
            },
        ),
    ],
)
def test_eur_lex_adapter_fetches_known_celex(citation: str, expected: dict[str, str]) -> None:
    adapter = EurLexHierarchyAdapter()
    result = adapter.fetch(citation)
    payload = json.loads(result.content.decode("utf-8"))
    assert payload["title"] == expected["title"]
    assert payload["jurisdiction"] == expected["jurisdiction"]
    assert "canonical_url" in payload
    assert payload["canonical_url"].startswith("https://eur-lex.europa.eu")
    assert result.metadata["source_family"] == "eur_lex"
    assert result.metadata["authority_yield"] == "high"


class DummyResponse:
    status_code = 200

    def __init__(self, text: str) -> None:
        self.text = text

    def raise_for_status(self) -> None:
        return None


def test_eur_lex_adapter_prefers_live_resolution(monkeypatch) -> None:
    def fake_get(url: str, timeout: int) -> DummyResponse:
        assert url == build_celex_url("32018L2001")
        return DummyResponse("<html><title>Live CELEX Title</title></html>")

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setenv("SENSIBLAW_EUR_LEX_LIVE", "1")
    adapter = EurLexHierarchyAdapter()
    result = adapter.fetch("CELEX:32018L2001")
    payload = json.loads(result.content.decode("utf-8"))
    assert payload["live_title"] == "Live CELEX Title"
    assert result.metadata["resolution_mode"] == "live"


def test_eur_lex_adapter_falls_back_when_live_fails(monkeypatch) -> None:
    def raising_get(url: str, timeout: int) -> None:
        raise requests.RequestException("timeout")

    monkeypatch.setattr(requests, "get", raising_get)
    monkeypatch.delenv("SENSIBLAW_EUR_LEX_LIVE", raising=False)
    adapter = EurLexHierarchyAdapter()
    result = adapter.fetch("CELEX:32018L2001")
    assert result.metadata["resolution_mode"] == "static_catalog"


def test_eur_lex_adapter_rejects_unknown_celex() -> None:
    adapter = EurLexHierarchyAdapter()
    with pytest.raises(ValueError):
        adapter.fetch("CELEX:99999")
