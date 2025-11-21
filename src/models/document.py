from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional
import json

from .provision import Provision
from .sentence import Sentence


@dataclass
class DocumentTOCEntry:
    """Structured representation of a table-of-contents entry."""

    node_type: Optional[str] = None
    identifier: Optional[str] = None
    title: Optional[str] = None
    page_number: Optional[int] = None
    children: List["DocumentTOCEntry"] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_type": self.node_type,
            "identifier": self.identifier,
            "title": self.title,
            "page_number": self.page_number,
            "children": [child.to_dict() for child in self.children],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocumentTOCEntry":
        return cls(
            node_type=data.get("node_type"),
            identifier=data.get("identifier"),
            title=data.get("title"),
            page_number=data.get("page_number"),
            children=[cls.from_dict(child) for child in data.get("children", [])],
        )


@dataclass
class DocumentMetadata:
    """Metadata about a legal document.

    Attributes:
        jurisdiction: Geographic or political jurisdiction of the document.
        citation: Formal citation or identifier for the document.
        date: Date the document was issued.
        title: Human-readable title or heading of the document.
        court: Optional court or body issuing the document.
        lpo_tags: Optional list of Legal Policy Objective tags.
        cco_tags: Optional list of cross-cultural obligation tags.
        cultural_flags: Optional list of cultural sensitivity flags.
        cultural_annotations: Derived annotations about cultural overlays.
            Each annotation is a mapping describing the applied policy.
        cultural_redactions: Flags whose rules redacted content.
        cultural_consent_required: Whether any cultural rule requires consent.
        jurisdiction_codes: Optional list of standardized jurisdiction codes.
        ontology_tags: Mapping of ontology names to matched tags.
        source_url: URL from which the document was retrieved.
        retrieved_at: Timestamp when the document was fetched.
        checksum: Optional checksum of the document contents.
        licence: Licence under which the document text is distributed.
    """

    jurisdiction: str
    citation: str
    date: date
    title: Optional[str] = None
    court: Optional[str] = None
    lpo_tags: Optional[List[str]] = None
    cco_tags: Optional[List[str]] = None
    cultural_flags: Optional[List[str]] = None
    cultural_annotations: List[Dict[str, Any]] = field(default_factory=list)
    cultural_redactions: List[str] = field(default_factory=list)
    cultural_consent_required: bool = False
    canonical_id: Optional[str] = None
    provenance: Optional[str] = None

    jurisdiction_codes: List[str] = field(default_factory=list)
    ontology_tags: Dict[str, List[str]] = field(default_factory=dict)
    source_url: Optional[str] = None
    retrieved_at: Optional[datetime] = None
    checksum: Optional[str] = None
    licence: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize metadata to a dictionary."""
        data = asdict(self)
        data["date"] = self.date.isoformat()
        if self.retrieved_at:
            data["retrieved_at"] = self.retrieved_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocumentMetadata":
        """Deserialize metadata from a dictionary."""
        parsed_date = (
            data["date"]
            if isinstance(data["date"], date)
            else datetime.fromisoformat(data["date"]).date()
        )
        retrieved = data.get("retrieved_at")
        if retrieved and not isinstance(retrieved, datetime):
            retrieved = datetime.fromisoformat(retrieved)

        return cls(
            jurisdiction=data["jurisdiction"],
            citation=data["citation"],
            date=parsed_date,
            title=data.get("title"),
            court=data.get("court"),
            lpo_tags=data.get("lpo_tags"),
            cco_tags=data.get("cco_tags"),
            cultural_flags=data.get("cultural_flags"),
            cultural_annotations=[
                entry
                if isinstance(entry, dict)
                else {
                    "kind": "legacy",
                    "text": str(entry),
                }
                for entry in data.get("cultural_annotations", [])
            ],
            cultural_redactions=list(data.get("cultural_redactions", [])),
            cultural_consent_required=bool(
                data.get("cultural_consent_required", False)
            ),
            canonical_id=data.get("canonical_id"),
            provenance=data.get("provenance"),
            jurisdiction_codes=list(data.get("jurisdiction_codes", [])),
            ontology_tags=dict(data.get("ontology_tags", {})),
            source_url=data.get("source_url"),
            retrieved_at=retrieved,
            checksum=data.get("checksum"),
            licence=data.get("licence"),
        )


@dataclass
class Document:
    """Representation of a legal document including metadata, body text,
    and any extracted provisions."""

    metadata: DocumentMetadata
    body: str
    provisions: List[Provision] = field(default_factory=list)
    toc_entries: List[DocumentTOCEntry] = field(default_factory=list)
    sentences: List[Sentence] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.body and not self.sentences:
            from src.text.sentences import segment_sentences

            self.sentences = segment_sentences(self.body)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the document to a dictionary."""
        return {
            "metadata": self.metadata.to_dict(),
            "body": self.body,
            "provisions": [p.to_dict() for p in self.provisions],
            "toc_entries": [entry.to_dict() for entry in self.toc_entries],
            "sentences": [sentence.to_dict() for sentence in self.sentences],
        }

    def to_json(self) -> str:
        """Serialize the document to a JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Document":
        """Deserialize a document from a dictionary."""
        metadata = DocumentMetadata.from_dict(data["metadata"])
        provisions = [Provision.from_dict(p) for p in data.get("provisions", [])]
        toc_entries = [
            DocumentTOCEntry.from_dict(entry) for entry in data.get("toc_entries", [])
        ]
        sentences = [Sentence.from_dict(item) for item in data.get("sentences", [])]
        return cls(
            metadata=metadata,
            body=data["body"],
            provisions=provisions,
            toc_entries=toc_entries,
            sentences=sentences,
        )

    @classmethod
    def from_json(cls, data: str) -> "Document":
        """Deserialize a document from a JSON string."""
        return cls.from_dict(json.loads(data))


__all__ = ["Document", "DocumentMetadata", "DocumentTOCEntry"]
