from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional
import json

from .provision import Provision


@dataclass
class DocumentMetadata:
    """Metadata about a legal document.

    Attributes:
        jurisdiction: Geographic or political jurisdiction of the document.
        citation: Formal citation or identifier for the document.
        date: Date the document was issued.
        court: Optional court or body issuing the document.
        lpo_tags: Optional list of Legal Policy Objective tags.
        cco_tags: Optional list of cross-cultural obligation tags.
        cultural_flags: Optional list of cultural sensitivity flags.
        jurisdiction_codes: Optional list of standardized jurisdiction codes.
        ontology_tags: Mapping of ontology names to matched tags.
    """

    jurisdiction: str
    citation: str
    date: date
    court: Optional[str] = None
    lpo_tags: Optional[List[str]] = None
    cco_tags: Optional[List[str]] = None
    cultural_flags: Optional[List[str]] = None
    canonical_id: Optional[str] = None
    provenance: Optional[str] = None

    jurisdiction_codes: List[str] = field(default_factory=list)
    ontology_tags: Dict[str, List[str]] = field(default_factory=dict)


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
            lpo_tags=data.get("lpo_tags"),
            cco_tags=data.get("cco_tags"),
            cultural_flags=data.get("cultural_flags"),
            canonical_id=data.get("canonical_id"),
            provenance=data.get("provenance"),

            jurisdiction_codes=list(data.get("jurisdiction_codes", [])),
            ontology_tags=dict(data.get("ontology_tags", {})),
        )


@dataclass
class Document:
    """Representation of a legal document including metadata, body text,
    and any extracted provisions."""

    metadata: DocumentMetadata
    body: str
    provisions: List[Provision] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the document to a dictionary."""
        return {
            "metadata": self.metadata.to_dict(),
            "body": self.body,
            "provisions": [p.to_dict() for p in self.provisions],
        }

    def to_json(self) -> str:
        """Serialize the document to a JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Document":
        """Deserialize a document from a dictionary."""
        metadata = DocumentMetadata.from_dict(data["metadata"])
        provisions = [Provision.from_dict(p) for p in data.get("provisions", [])]
        return cls(metadata=metadata, body=data["body"], provisions=provisions)

    @classmethod
    def from_json(cls, data: str) -> "Document":
        """Deserialize a document from a JSON string."""
        return cls.from_dict(json.loads(data))


__all__ = ["Document", "DocumentMetadata"]
