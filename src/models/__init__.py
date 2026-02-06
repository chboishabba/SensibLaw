"""Model classes used throughout the project."""

from .document import Document, DocumentMetadata
from .provision import Provision
from .sentence import Sentence
from .text_span import TextSpan

__all__ = ["Document", "DocumentMetadata", "Provision", "Sentence", "TextSpan"]
