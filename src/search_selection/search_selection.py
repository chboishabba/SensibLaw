from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class SearchQuery:
    source_label: str
    query_text: str
    language: str = "en"


@dataclass(frozen=True)
class SearchResult:
    source_label: str
    query_text: str
    metadata: Mapping[str, object] = field(default_factory=dict)
