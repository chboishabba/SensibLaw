"""Sentence data model for segmented document text."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class Sentence:
    """A sentence extracted from a document body."""

    text: str
    start_char: int
    end_char: int
    index: int

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the sentence to a dictionary."""

        return {
            "text": self.text,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "index": self.index,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Sentence":
        """Deserialize a :class:`Sentence` from ``data``."""

        return cls(
            text=str(data.get("text", "")),
            start_char=int(data.get("start_char", 0)),
            end_char=int(data.get("end_char", 0)),
            index=int(data.get("index", 0)),
        )


__all__ = ["Sentence"]

