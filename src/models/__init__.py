"""Model classes used throughout the project."""

from .attribution_claims import Attribution, ExtractionRecord, SourceEntity
from .document import Document, DocumentMetadata
from .provision import Provision
from .sentence import Sentence
from .numeric_claims import Magnitude, QuantifiedClaim, RangeClaim, RatioClaim, NumericSurface
from .text_span import TextSpan

__all__ = [
    "Attribution",
    "Document",
    "DocumentMetadata",
    "ExtractionRecord",
    "Magnitude",
    "NumericSurface",
    "Provision",
    "QuantifiedClaim",
    "RangeClaim",
    "RatioClaim",
    "Sentence",
    "SourceEntity",
    "TextSpan",
]
