from __future__ import annotations

import requests
from typing import Any, Mapping

from src.sources.normalized_source import build_normalized_source_unit

__all__ = [
    "normalize_worldbank_source",
    "mock_worldbank_bundle",
    "fetch_live_worldbank_report",
]


def normalize_worldbank_source(
    *,
    doc_id: str,
    title: str,
    url: str,
    primary_language: str = "en",
    translation_status: str = "original",
    live_status: str = "live",
    provenance: str = "worldbank.org",
) -> dict[str, Any]:
    source_id = f"worldbank:{doc_id}:{primary_language}"
    return build_normalized_source_unit(
        source_id=source_id,
        source_family="worldbank",
        jurisdiction="global",
        authority_level="development",
        source_type="report",
        title=title,
        url=url,
        section=doc_id,
        version="publication",
        live_status=live_status,
        primary_language=primary_language,
        translation_status=translation_status,
        translation_provenance=provenance,
        provenance=provenance,
    )


def mock_worldbank_bundle() -> list[Mapping[str, Any]]:
    return [
        normalize_worldbank_source(
            doc_id="WDR2021",
            title="World Development Report 2021",
            url="https://documents.worldbank.org/en/publication/documents-reports/documentdetail/401781609909355252/world-development-report-2021",
        )
    ]


def fetch_live_worldbank_report(*, doc_id: str, url: str, timeout: int = 10) -> dict[str, Any] | None:
    try:
        response = requests.head(url, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException:
        return None
    return normalize_worldbank_source(doc_id=doc_id, title="World Bank Document", url=url)
