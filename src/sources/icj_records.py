from __future__ import annotations

import requests
from typing import Any, Mapping

from src.sources.normalized_source import build_normalized_source_unit

ICJ_BASE_URL = "https://www.icj-cij.org"


def normalize_icj_source(
    *,
    record_id: str,
    title: str,
    url: str,
    primary_language: str = "en",
    translation_status: str = "original",
    live_status: str = "live",
    provenance: str = "icj-cij.org",
) -> dict[str, Any]:
    return build_normalized_source_unit(
        source_id=f"icj:{record_id}:{primary_language}",
        source_family="icj_cases",
        jurisdiction="international",
        authority_level="court",
        source_type="judgment",
        title=title,
        url=url,
        section=record_id,
        version="publication",
        live_status=live_status,
        primary_language=primary_language,
        translation_status=translation_status,
        translation_provenance=provenance,
        provenance=provenance,
    )


def mock_icj_bundle() -> list[Mapping[str, Any]]:
    return [
        normalize_icj_source(
            record_id="170-20201112-ADV-01-00-EN",
            title="Advisory Opinion on the Israeli Wall",
            url=f"{ICJ_BASE_URL}/sites/default/files/case-related/170/170-20201112-ADV-01-00-EN.pdf",
        )
    ]


def fetch_live_icj_record(*, record_id: str, url: str, timeout: int = 10) -> dict[str, Any] | None:
    try:
        response = requests.head(url, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException:
        return None
    return normalize_icj_source(record_id=record_id, title="ICJ Record", url=url)
