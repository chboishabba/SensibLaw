"""Utility functions for ingesting raw records into :class:`Document` objects."""

from typing import Any, Dict

from ..models.document import Document
from ..ontology.tagger import tag_text


def emit_document(record: Dict[str, Any]) -> Document:
    """Convert a raw record dictionary into a tagged :class:`Document` instance."""
    doc = Document.from_dict(record)
    if not doc.provisions:
        doc.provisions = [tag_text(doc.body)]
    return doc


def emit_document_from_json(data: str) -> Document:
    """Convert a JSON string into a tagged :class:`Document` instance."""
    doc = Document.from_json(data)
    if not doc.provisions:
        doc.provisions = [tag_text(doc.body)]
    return doc
