from __future__ import annotations

import json
import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from collections.abc import Mapping
from typing import Any

import requests

from src.sources.normalized_source import build_normalized_source_unit

LOGGER = logging.getLogger(__name__)

LEGISLATION_BASE_URL = "https://www.legislation.gov.uk"
DEFAULT_LEGISLATION_ACT = "ukpga/2018/16"
DEFAULT_SECTION_LIMIT = 8
DEFAULT_VERSION_SUFFIX = "enacted"
_SECTION_RE = re.compile(r"/section/([^/]+)")


def _load_fixture(filename: str) -> dict[str, Any]:
    fixture_path = (
        Path(__file__).resolve().parents[2]
        / "tests"
        / "fixtures"
        / "zelph"
        / filename
    )
    if not fixture_path.exists():
        return {}
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def load_uk_legislation_follow_candidates() -> dict[str, list[dict[str, Any]]]:
    payload = _load_fixture("gwb_uk_legislation_follow_candidate.json")
    sample = load_uk_legislation_api_sample()
    sample_title = sample.get("title") or "UK legislation"
    sample_date = sample.get("documentDate")
    enriched_rows = _annotate_fixture_receipts(
        list(payload.get("source_review_rows") or []),
        title=sample_title,
        document_date=sample_date,
        version=DEFAULT_VERSION_SUFFIX,
    )
    return {
        "review_item_rows": list(payload.get("review_item_rows") or []),
        "source_review_rows": enriched_rows,
    }


def _annotate_fixture_receipts(
    rows: list[dict[str, Any]],
    *,
    title: str | None,
    document_date: str | None,
    version: str,
) -> list[dict[str, Any]]:
    for row in rows:
        receipts = row.get("receipts") or []
        annotated: list[dict[str, Any]] = []
        for receipt in receipts:
            if isinstance(receipt, Mapping):
                url = str(
                    receipt.get("value")
                    or receipt.get("url")
                    or receipt.get("link")
                    or receipt.get("href")
                    or ""
                ).strip()
            else:
                url = str(receipt or "").strip()
            if not url:
                continue
            annotated.append(
                _annotate_legislation_receipt(
                    url,
                    title=title,
                    document_date=document_date,
                    version=version,
                )
            )
        if annotated:
            row["receipts"] = annotated
    return rows


def load_uk_legislation_api_sample() -> dict[str, Any]:
    return _load_fixture("legislation_gov_uk_sample.json")


def parse_legislation_xml(
    xml_content: bytes,
    *,
    max_sections: int = DEFAULT_SECTION_LIMIT,
    version_suffix: str = DEFAULT_VERSION_SUFFIX,
) -> dict[str, Any]:
    ns = {
        "leg": "http://www.legislation.gov.uk/namespaces/legislation",
        "ukm": "http://www.legislation.gov.uk/namespaces/metadata",
        "dc": "http://purl.org/dc/elements/1.1/",
        "dct": "http://purl.org/dc/terms/",
    }
    root = ET.fromstring(xml_content)
    metadata = root.find("ukm:Metadata", namespaces=ns)
    title = None
    document_date = None
    if metadata is not None:
        title_el = metadata.find("{http://purl.org/dc/elements/1.1/}title")
        title = title_el.text if title_el is not None else None
        date_el = metadata.find("{http://purl.org/dc/terms/}valid")
        if date_el is None:
            date_el = metadata.find("{http://purl.org/dc/elements/1.1/}modified")
        document_date = date_el.text if date_el is not None else None

    body = root.find(".//leg:Body", namespaces=ns)
    sections: list[dict[str, str]] = []
    seen_sections: set[tuple[str, str]] = set()
    if body is not None and max_sections > 0:
        for section in body.findall(".//leg:P1", namespaces=ns):
            document_uri = section.get("DocumentURI")
            if not document_uri or "/section/" not in document_uri:
                continue
            section_number = document_uri.split("/section/", 1)[1].strip("/")
            if not section_number:
                continue
            section_url = document_uri.replace("http://", "https://", 1).rstrip("/")
            if version_suffix:
                section_url = f"{section_url}/{version_suffix.lstrip('/')}"
            section_key = (section_number, section_url)
            if section_key in seen_sections:
                continue
            seen_sections.add(section_key)
            sections.append(
                {
                    "sectionNumber": section_number,
                    "url": section_url,
                    "sectionLabel": _format_section_label(section_number),
                    "version": version_suffix,
                }
            )
            if len(sections) >= max_sections:
                break

    return {
        "title": title,
        "documentDate": document_date,
        "sections": sections,
    }


def _format_section_label(section_number: str) -> str:
    cleaned = section_number.replace("/", " ").replace("-", " ").strip()
    return cleaned or section_number or ""


def fetch_legislation_act_payload(
    *,
    act_id: str = DEFAULT_LEGISLATION_ACT,
    max_sections: int = DEFAULT_SECTION_LIMIT,
    version_suffix: str = DEFAULT_VERSION_SUFFIX,
    timeout: int = 15,
) -> dict[str, Any]:
    url = f"{LEGISLATION_BASE_URL}/{act_id}/data.xml"
    headers = {"Accept": "application/xml"}
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        LOGGER.debug("failed to fetch legislation payload %s", url, exc_info=exc)
        return {}
    try:
        return parse_legislation_xml(
            response.content,
            max_sections=max_sections,
            version_suffix=version_suffix,
        )
    except ET.ParseError as exc:
        LOGGER.debug("failed to parse legislation payload %s", url, exc_info=exc)
        return {}


def normalize_legislation_receipts(
    *,
    act_id: str = DEFAULT_LEGISLATION_ACT,
    max_sections: int = DEFAULT_SECTION_LIMIT,
    version_suffix: str = DEFAULT_VERSION_SUFFIX,
) -> list[dict[str, Any]]:
    payload = fetch_legislation_act_payload(
        act_id=act_id,
        max_sections=max_sections,
        version_suffix=version_suffix,
    )
    if not payload or not payload.get("sections"):
        payload = load_uk_legislation_api_sample()
    sections = list(payload.get("sections") or [])[:max_sections]
    receipts: list[dict[str, Any]] = []
    for section in sections:
        receipts.append(
            _annotate_legislation_receipt(
                section.get("url"),
                title=payload.get("title"),
                document_date=payload.get("documentDate"),
                version=section.get("version") or version_suffix,
            )
        )
    return receipts


def _annotate_legislation_receipt(
    url: str | None,
    *,
    title: str | None,
    document_date: str | None,
    version: str,
) -> dict[str, Any]:
    url = str(url or "").strip()
    section_number = _extract_section_number(url)
    section_label = _format_section_label(section_number)
    title_label = title or "UK legislation"
    section_token = section_label or section_number or "section"
    label_value = f"{title_label} section {section_token}".strip()
    metadata = {
        "section": section_number,
        "section_label": section_token,
        "title": title_label,
        "documentDate": document_date,
        "version": version,
        "live_title": label_value,
        "resolution_mode": "live_legislation_receipt",
        "cite_class": "uk_legislation",
    }
    normalized = build_normalized_source_unit(
        source_id=f"legislation.gov.uk:{section_token}:{version}",
        source_family="uk_legislation",
        jurisdiction="uk",
        authority_level="statute",
        source_type="section",
        title=label_value,
        url=url,
        section=section_token,
        version=version,
        live_status="live",
        primary_language="en",
        translation_status="original",
        provenance="legislation.gov.uk",
    )
    metadata["normalized_source_unit"] = normalized
    return {
        "kind": "source_link",
        "value": url,
        "label": label_value,
        "metadata": metadata,
    }


def _extract_section_number(url: str) -> str:
    match = _SECTION_RE.search(url)
    return match.group(1) if match else ""
