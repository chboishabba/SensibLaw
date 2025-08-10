"""Utility functions for ingesting raw records into :class:`Document` objects."""

from typing import Any, Dict

from models.document import Document


def emit_document(record: Dict[str, Any]) -> Document:
    """Convert a raw record dictionary into a :class:`Document` instance."""
    return Document.from_dict(record)


def emit_document_from_json(data: str) -> Document:
    """Convert a JSON string into a :class:`Document` instance."""
    return Document.from_json(data)
