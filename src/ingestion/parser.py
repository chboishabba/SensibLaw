"""Utility functions for ingesting raw records into :class:`Document` objects."""

import json
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

from models.document import Document
from .consent_gate import check_consent


def emit_document(record: Dict[str, Any]) -> Document:
    """Convert a raw record dictionary into a :class:`Document` instance.

    The record is evaluated by the consent gate before being converted to a
    :class:`Document`. If policy checks fail, a :class:`ConsentError` is
    raised to block unauthorized persistence or transmission.
    """

    check_consent(record)
    return Document.from_dict(record)


def emit_document_from_json(data: str) -> Document:
    """Convert a JSON string into a :class:`Document` instance.

    The JSON payload is decoded and passed through the consent gate before the
    resulting record is converted to a :class:`Document`.
    """

    record = json.loads(data)
    check_consent(record)
    return Document.from_dict(record)
