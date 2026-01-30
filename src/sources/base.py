from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class FetchResult:
    content: bytes
    content_type: str | None
    url: str
    metadata: dict


class LegalSourceAdapter(Protocol):
    source_name: str

    def fetch(self, citation: str) -> FetchResult:
        """Fetch raw bytes for a citation (PDF/HTML). Must be deterministic wrt request inputs."""
