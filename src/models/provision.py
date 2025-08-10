from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class Provision:
    """A discrete provision within a legal document."""

    text: str
    principles: List[str] = field(default_factory=list)
    customs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the provision to a dictionary."""
        return {
            "text": self.text,
            "principles": list(self.principles),
            "customs": list(self.customs),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Provision":
        """Deserialize a provision from a dictionary."""
        return cls(
            text=data["text"],
            principles=list(data.get("principles", [])),
            customs=list(data.get("customs", [])),
        )
