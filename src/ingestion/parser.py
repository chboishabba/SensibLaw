"""Utility functions for ingesting raw records into :class:`Document` objects."""

import json
from typing import Any, Dict, List

from ..models.document import Document
from ..models.provision import Provision
from ..ontology.tagger import tag_provision
from .consent_gate import check_consent

# Mapping of human-readable jurisdictions to standard codes.
JURISDICTION_MAP = {
    "Australia": ["AU"],
    "AUS": ["AU"],
    "AU": ["AU"],
}


def _apply_tags(doc: Document, tags: Dict[str, List[str]]) -> None:
    """Populate ontology tags on the document metadata."""
    doc.metadata.ontology_tags = tags
    # Populate legacy fields for backward compatibility
    if "lpo" in tags:
        doc.metadata.lpo_tags = tags["lpo"]
    if "cco" in tags:
        doc.metadata.cco_tags = tags["cco"]


def _apply_jurisdiction_codes(doc: Document) -> None:
    """Add jurisdiction codes if they can be inferred."""
    if not doc.metadata.jurisdiction_codes:
        doc.metadata.jurisdiction_codes = JURISDICTION_MAP.get(
            doc.metadata.jurisdiction, []
        )


def emit_document(record: Dict[str, Any]) -> Document:
    """Convert a raw record dictionary into a tagged :class:`Document` instance."""
    check_consent(record)
    doc = Document.from_dict(record)
    provision = Provision(text=record["body"])
    tags = tag_provision(provision)
    doc.provisions = [provision]
    _apply_tags(doc, tags)
    _apply_jurisdiction_codes(doc)
    return doc


def emit_document_from_json(data: str) -> Document:
    """Convert a JSON string into a tagged :class:`Document` instance."""
    record = json.loads(data)
    check_consent(record)
    doc = Document.from_dict(record)
    provision = Provision(text=record["body"])
    tags = tag_provision(provision)
    doc.provisions = [provision]
    _apply_tags(doc, tags)
    _apply_jurisdiction_codes(doc)
    return doc
