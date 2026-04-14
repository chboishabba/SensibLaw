from __future__ import annotations

import re
from typing import Any, Mapping

import requests

from src.sources.normalized_source import build_normalized_source_unit

_UNDOCS_BASE_URL = "https://undocs.org"
_TITLE_RE = re.compile(r"<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_ENGLISH_LINK_RE_TEMPLATE = r'href=["\'](/en/{symbol})["\']'
_SELECTOR_TITLES = {"select a language", "document viewer"}


def normalize_undoc_source(
    *,
    symbol: str,
    title: str,
    url: str,
    language: str = "en",
    translation_status: str = "original",
    translation_provenance: str | None = None,
    live_status: str = "live",
) -> dict[str, Any]:
    source_id = f"undocs:{symbol}:{language}"
    return build_normalized_source_unit(
        source_id=source_id,
        source_family="undocs",
        jurisdiction="global",
        authority_level="treaty",
        source_type="resolution",
        title=title,
        url=url,
        section=symbol,
        version="publication",
        live_status=live_status,
        primary_language=language,
        translation_status=translation_status,
        translation_provenance=translation_provenance,
        provenance="undocs.org",
    )


def mock_undoc_bundle() -> list[Mapping[str, Any]]:
    return [
        normalize_undoc_source(
            symbol="INFCIRC/12/Rev.1",
            title="Treaty on the Non-Proliferation of Nuclear Weapons",
            url="https://undocs.org/INFCIRC/12/Rev.1",
        )
    ]


def fetch_live_undoc(symbol: str, *, language: str = "en", timeout: int = 10) -> dict[str, Any] | None:
    try:
        response = requests.get(f"{_UNDOCS_BASE_URL}/{symbol}", timeout=timeout)
        response.raise_for_status()
    except requests.RequestException:
        return None
    if language == "en":
        pattern = _ENGLISH_LINK_RE_TEMPLATE.format(symbol=re.escape(symbol))
        link = re.search(pattern, response.text)
        if link:
            try:
                english_response = requests.get(
                    f"{_UNDOCS_BASE_URL}{link.group(1)}",
                    timeout=timeout,
                    headers={"Accept-Language": "en"},
                )
                english_response.raise_for_status()
                response = english_response
            except requests.RequestException:
                pass
    final_url = response.url
    iframe_match = re.search(r"<iframe[^>]+src=['\"]([^'\"\s]+api/symbol/access[^'\"]+)['\"]", response.text)
    if iframe_match:
        try:
            final_url = iframe_match.group(1).replace("&amp;", "&")
            pdf_response = requests.head(final_url, timeout=timeout)
            pdf_response.raise_for_status()
        except requests.RequestException:
            pass
    match = _TITLE_RE.search(response.text)
    title = match.group(1).strip() if match else symbol
    if title.lower() in _SELECTOR_TITLES:
        title = f"UN document {symbol}"
    return normalize_undoc_source(
        symbol=symbol,
        title=title,
        url=final_url,
        language=language,
        translation_status="original" if language == "en" else "translated",
        translation_provenance="undocs.org",
        live_status="live",
    )


def normalized_undoc_symbol(symbol: str = "INFCIRC/12/Rev.1", *, language: str = "en") -> dict[str, Any]:
    payload = fetch_live_undoc(symbol, language=language)
    if payload:
        return payload
    return mock_undoc_bundle()[0]
