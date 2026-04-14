from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class NormalizedSourceUnit:
    source_id: str
    source_family: str
    jurisdiction: str
    authority_level: str
    source_type: str
    title: str
    url: str
    section: str | None = None
    version: str | None = None
    live_status: str = "live"
    primary_language: str = "en"
    translation_status: str = "original"
    translation_provenance: str | None = None
    provenance: str | None = None
    readiness_signals: Mapping[str, bool] | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key in list(data.keys()):
            if data[key] is None:
                data.pop(key)
        return data


def build_normalized_source_unit(
    source_id: str,
    *,
    source_family: str,
    jurisdiction: str,
    authority_level: str,
    source_type: str,
    title: str,
    url: str,
    section: str | None = None,
    version: str | None = None,
    live_status: str = "live",
    primary_language: str = "en",
    translation_status: str = "original",
    translation_provenance: str | None = None,
    provenance: str | None = None,
    readiness_signals: Mapping[str, bool] | None = None,
) -> dict[str, Any]:
    return NormalizedSourceUnit(
        source_id=source_id,
        source_family=source_family,
        jurisdiction=jurisdiction,
        authority_level=authority_level,
        source_type=source_type,
        title=title,
        url=url,
        section=section,
        version=version,
        live_status=live_status,
        provenance=provenance,
        readiness_signals=readiness_signals,
    ).to_dict()
