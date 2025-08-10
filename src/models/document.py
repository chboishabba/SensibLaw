from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date, datetime
from typing import Any, Dict, Optional
import json


@dataclass
class DocumentMetadata:
    """Metadata about a legal document.

    Attributes:
        jurisdiction: Geographic or political jurisdiction of the document.
        citation: Formal citation or identifier for the document.
        date: Date the document was issued.
        court: Optional court or body issuing the document.
    """

    jurisdiction: str
    citation: str
    date: date
    court: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize metadata to a dictionary."""
        data = asdict(self)
        data["date"] = self.date.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocumentMetadata":
        """Deserialize metadata from a dictionary."""
        parsed_date = (
            data["date"]
            if isinstance(data["date"], date)
            else datetime.fromisoformat(data["date"]).date()
        )
        return cls(
            jurisdiction=data["jurisdiction"],
            citation=data["citation"],
            date=parsed_date,
            court=data.get("court"),
        )


@dataclass
class Document:
    """Representation of a legal document including metadata and body text."""

    metadata: DocumentMetadata
    body: str

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the document to a dictionary."""
        return {"metadata": self.metadata.to_dict(), "body": self.body}

    def to_json(self) -> str:
        """Serialize the document to a JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Document":
        """Deserialize a document from a dictionary."""
        metadata = DocumentMetadata.from_dict(data["metadata"])
        return cls(metadata=metadata, body=data["body"])

    @classmethod
    def from_json(cls, data: str) -> "Document":
        """Deserialize a document from a JSON string."""
        return cls.from_dict(json.loads(data))
