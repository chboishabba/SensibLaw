from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class TextSpan:
    """Canonical text span anchored to a document revision."""

    revision_id: str
    start_char: int
    end_char: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "revision_id": self.revision_id,
            "start_char": self.start_char,
            "end_char": self.end_char,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TextSpan":
        return cls(
            revision_id=str(data.get("revision_id", "")),
            start_char=int(data.get("start_char", 0)),
            end_char=int(data.get("end_char", 0)),
        )


__all__ = ["TextSpan"]
