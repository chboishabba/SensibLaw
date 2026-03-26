from __future__ import annotations

import csv
import io
import re
from pathlib import Path
from typing import Any
from typing import Mapping
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from src.reporting.structure_report import TextUnit


_GOOGLE_HOSTS = {"docs.google.com"}
_USER_AGENT = "Mozilla/5.0"


def _clean_line(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\ufeff", " ")).strip()


def parse_google_public_url(url: str) -> dict[str, str]:
    parsed = urlparse(str(url).strip())
    if parsed.netloc not in _GOOGLE_HOSTS:
        raise ValueError(f"unsupported host: {parsed.netloc}")
    match = re.search(r"^/(document|spreadsheets)/d/([A-Za-z0-9_-]+)", parsed.path)
    if not match:
        raise ValueError(f"unsupported Google Docs/Sheets path: {parsed.path}")
    kind = "doc" if match.group(1) == "document" else "sheet"
    return {"kind": kind, "doc_id": match.group(2)}


def build_google_public_export_url(url: str) -> str:
    parsed = parse_google_public_url(url)
    if parsed["kind"] == "doc":
        return f"https://docs.google.com/document/d/{parsed['doc_id']}/export?format=txt"
    return f"https://docs.google.com/spreadsheets/d/{parsed['doc_id']}/export?format=csv"


def fetch_google_public_export_text(url: str, *, timeout: int = 20) -> str:
    export_url = build_google_public_export_url(url)
    request = Request(export_url, headers={"User-Agent": _USER_AGENT})
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def load_google_doc_units_from_text(text: str, *, source_id: str) -> list[TextUnit]:
    lines = [_clean_line(line) for line in text.splitlines()]
    paragraphs = [line for line in lines if line]
    return [
        TextUnit(
            unit_id=f"{source_id}:p{index}",
            source_id=source_id,
            source_type="google_doc_public",
            text=paragraph,
        )
        for index, paragraph in enumerate(paragraphs, start=1)
    ]


def load_google_doc_units_from_url(url: str) -> list[TextUnit]:
    parsed = parse_google_public_url(url)
    if parsed["kind"] != "doc":
        raise ValueError("url is not a Google Doc")
    text = fetch_google_public_export_text(url)
    return load_google_doc_units_from_text(text, source_id=f"google_doc:{parsed['doc_id']}")


def _row_to_text(row: Mapping[str, Any]) -> str:
    parts: list[str] = []
    event = _clean_line(str(row.get("Event") or ""))
    description = _clean_line(str(row.get("Description") or ""))
    if event:
        parts.append(f"Event: {event}")
    if description:
        parts.append(f"Description: {description}")
    evidenced = _clean_line(str(row.get("Evidenced") or ""))
    if evidenced:
        parts.append(f"Evidenced: {evidenced}")
    type_value = _clean_line(str(row.get("Type") or ""))
    if type_value:
        parts.append(f"Type: {type_value}")
    filename = _clean_line(str(row.get("Filename") or ""))
    if filename:
        parts.append(f"Filename: {filename}")
    id_as_is = _clean_line(str(row.get("ID as is") or ""))
    if id_as_is:
        parts.append(f"Source id: {id_as_is}")
    return " | ".join(parts)


def load_google_sheet_units_from_csv_text(text: str, *, source_id: str) -> list[TextUnit]:
    reader = csv.DictReader(io.StringIO(text))
    units: list[TextUnit] = []
    for index, row in enumerate(reader, start=1):
        rendered = _row_to_text(row)
        if not rendered:
            continue
        unit_ref = _clean_line(str(row.get("ID#1") or row.get("ID#2") or row.get("ID as is") or index)) or str(index)
        units.append(
            TextUnit(
                unit_id=f"{source_id}:r{unit_ref}",
                source_id=source_id,
                source_type="google_sheet_public",
                text=rendered,
            )
        )
    return units


def load_google_sheet_units_from_url(url: str) -> list[TextUnit]:
    parsed = parse_google_public_url(url)
    if parsed["kind"] != "sheet":
        raise ValueError("url is not a Google Sheet")
    text = fetch_google_public_export_text(url)
    return load_google_sheet_units_from_csv_text(text, source_id=f"google_sheet:{parsed['doc_id']}")


def extract_affidavit_text_from_doc_text(text: str) -> str:
    cleaned = text.replace("\ufeff", "")
    marker = "Affidavit Text:"
    start = cleaned.find(marker)
    if start == -1:
        return cleaned.strip()
    after = cleaned[start + len(marker):].strip()
    stop_markers = [
        "Which Allegations Can You Plausibly Deny or Explain?",
        "Summary of Response",
        "Response to Affidavit of",
    ]
    end = len(after)
    for stop in stop_markers:
        idx = after.find(stop)
        if idx != -1:
            end = min(end, idx)
    return after[:end].strip()


def extract_contested_response_text_from_doc_text(text: str) -> str:
    cleaned = text.replace("\ufeff", "")
    start_markers = [
        "Summary of Response",
        "Responding to Affidavit",
    ]
    start = -1
    for marker in start_markers:
        idx = cleaned.rfind(marker)
        if idx != -1:
            start = max(start, idx)
    if start == -1:
        return cleaned.strip()
    return cleaned[start:].strip()


def load_google_public_units(url: str) -> list[TextUnit]:
    parsed = parse_google_public_url(url)
    if parsed["kind"] == "doc":
        return load_google_doc_units_from_url(url)
    return load_google_sheet_units_from_url(url)


__all__ = [
    "build_google_public_export_url",
    "extract_affidavit_text_from_doc_text",
    "extract_contested_response_text_from_doc_text",
    "fetch_google_public_export_text",
    "load_google_doc_units_from_text",
    "load_google_doc_units_from_url",
    "load_google_public_units",
    "load_google_sheet_units_from_csv_text",
    "load_google_sheet_units_from_url",
    "parse_google_public_url",
]
