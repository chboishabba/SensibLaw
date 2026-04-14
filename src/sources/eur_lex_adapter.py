from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Mapping, Optional

import requests

from .base import FetchResult, LegalSourceAdapter

CELEX_METADATA: dict[str, Mapping[str, str]] = {
    "32018L2001": {
        "title": "European Union (Withdrawal) Act 2018",
        "instrument_type": "UK statute",
        "jurisdiction": "United Kingdom",
        "publication_date": "2018-06-26",
        "summary": "Implements Article 50 TEU and provides framework for departing EU law.",
    },
    "32020D1144": {
        "title": "Treaty on European Union (simplified revision)",
        "instrument_type": "EU treaty",
        "jurisdiction": "European Union",
        "publication_date": "2020-04-17",
        "summary": "Adjusts institutional framework for EU cooperation post-withdrawal.",
    },
    "32017L1546": {
        "title": "Directive (EU) 2017/1546",
        "instrument_type": "EU directive",
        "jurisdiction": "European Union",
        "publication_date": "2017-08-30",
        "summary": "Relates to the quality of water intended for human consumption within the EU and retained UK law references.",
    },
}


def build_celex_url(celex_id: str) -> str:
    normalized = str(celex_id or "").strip().upper()
    if normalized.startswith("CELEX:"):
        normalized = normalized.split(":", 1)[1]
    return f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{normalized}"


def _normalize_celex(value: str) -> str:
    normalized = str(value or "").strip().upper()
    if normalized.startswith("CELEX:"):
        normalized = normalized.split(":", 1)[1]
    return normalized


def _parse_title(html: str) -> Optional[str]:
    match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return match.group(1).strip()


def _fetch_live_metadata(celex_id: str) -> Optional[dict[str, str]]:
    url = build_celex_url(celex_id)
    enabled = os.environ.get("SENSIBLAW_EUR_LEX_LIVE", "0").strip().lower() in {"1", "true", "yes"}
    if not enabled:
        return None
    try:
        response = requests.get(url, timeout=6)
        response.raise_for_status()
    except requests.RequestException:
        return None
    title = _parse_title(response.text)
    return {
        "live_title": title or f"CELEX {celex_id}",
        "status_code": str(response.status_code),
        "canonical_url": url,
    }


@dataclass(frozen=True)
class EurLexHierarchyAdapter(LegalSourceAdapter):
    source_name: str = "eur_lex"

    def fetch(self, citation: str) -> FetchResult:
        celex = _normalize_celex(citation)
        metadata = CELEX_METADATA.get(celex)
        if not metadata:
            raise ValueError(f"Unsupported CELEX identifier: {citation}")

        payload = {
            "celex": celex,
            "title": metadata["title"],
            "instrument_type": metadata["instrument_type"],
            "jurisdiction": metadata["jurisdiction"],
            "publication_date": metadata["publication_date"],
            "summary": metadata["summary"],
            "canonical_url": build_celex_url(celex),
        }

        live_metadata = _fetch_live_metadata(celex)
        metadata_attrs = {"source_family": "eur_lex", "authority_yield": "high", "celex_id": celex}
        if live_metadata:
            payload.update(live_metadata)
            metadata_attrs["resolution_mode"] = "live"
            payload["title"] = live_metadata.get("live_title") or payload["title"]
        else:
            metadata_attrs["resolution_mode"] = "static_catalog"

        content = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return FetchResult(
            content=content,
            content_type="application/json",
            url=payload["canonical_url"],
            metadata=metadata_attrs,
        )


__all__ = ["EurLexHierarchyAdapter", "CELEX_METADATA", "build_celex_url"]
