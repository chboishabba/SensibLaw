from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .base import FetchResult, LegalSourceAdapter


@dataclass(frozen=True)
class CourtListenerStatuteCase:
    case_id: str
    title: str
    citation: str
    court: str
    date: str
    url: str
    summary: str
    statutes: tuple[str, ...]
    precedent_kind: str | None


class CourtListenerStatuteAdapter(LegalSourceAdapter):
    source_name: str = "courtlistener.statute_cases"

    DEFAULT_DATA_PATH = (
        Path(__file__).resolve().parents[2] / "data" / "courtlistener_statute_cases.json"
    )

    def __init__(self, *, data_path: Path | None = None, data: dict[str, Any] | None = None) -> None:
        self._data_path = data_path or self.DEFAULT_DATA_PATH
        if data is not None:
            self._statute_cases = data
        else:
            self._statute_cases = self._load_data()

    def _load_data(self) -> dict[str, Any]:
        try:
            with self._data_path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except FileNotFoundError as exc:
            raise RuntimeError(f"CourtListener data file missing: {self._data_path}") from exc

    def fetch(self, citation: str) -> FetchResult:
        statute_key = str(citation or "").strip()
        payload = self._statute_cases.get(statute_key)
        if not isinstance(payload, dict):
            raise KeyError(f"Unknown statute identifier: {statute_key}")

        raw_cases = payload.get("cases") or []
        normalized_cases: list[dict[str, Any]] = []
        for row in raw_cases:
            statutes = tuple(str(token or "").strip() for token in (row.get("statutes") or []))
            case = {
                "case_id": str(row.get("case_id") or "").strip(),
                "title": str(row.get("title") or "").strip(),
                "citation": str(row.get("citation") or "").strip(),
                "court": str(row.get("court") or "").strip(),
                "date": str(row.get("date") or "").strip(),
                "url": str(row.get("url") or "").strip(),
                "summary": str(row.get("summary") or "").strip(),
                "statutes": [stat for stat in statutes if stat],
                "precedent_kind": str(row.get("precedent_kind") or "").strip() or None,
            }
            normalized_cases.append(case)

        case_payload = {
            "statute_id": statute_key,
            "title": str(payload.get("title") or "").strip(),
            "jurisdiction": str(payload.get("jurisdiction") or "").strip(),
            "statute_url": str(payload.get("statute_url") or "").strip(),
            "description": str(payload.get("description") or "").strip(),
            "cases": normalized_cases,
        }
        content = json.dumps(case_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        return FetchResult(
            content=content,
            content_type="application/json",
            url=case_payload["statute_url"],
            metadata={
                "source_family": "courtlistener_statutes",
                "statute_id": statute_key,
                "case_count": len(normalized_cases),
            },
        )


__all__ = ["CourtListenerStatuteAdapter"]
