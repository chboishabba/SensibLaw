import re
from dataclasses import dataclass
from typing import Dict, List, Optional

# Precompiled regex to capture leading numbering/heading from a block of text
HEADING_RE = re.compile(r"^(?P<number>\d+(?:\.\d+)*)\s+(?P<heading>.+)$")

# Single-pass combined regex mimicking an Aho–Corasick matcher for keywords
TOKEN_RE = re.compile(
    r"(?P<modality>must not|must|may)|"
    r"(?P<condition>if|unless|subject to|despite)|"
    r"(?P<xref>s\s+\d+[A-Za-z]?|this\s+Part)",
    re.IGNORECASE,
)


def _strip_tags(html: str) -> str:
    """Remove simple HTML tags, returning the text content."""
    return re.sub(r"<[^>]+>", "", html).strip()


@dataclass
class Section:
    """Representation of a single legislative section with extracted rules."""

    number: Optional[str]
    heading: Optional[str]
    text: str
    modality: Optional[str]
    conditions: List[str]
    references: List[str]

    def to_dict(self) -> Dict[str, object]:
        return {
            "number": self.number,
            "heading": self.heading,
            "text": self.text,
            "rules": {
                "modality": self.modality,
                "conditions": list(self.conditions),
                "references": list(self.references),
            },
        }


def parse_html_section(html: str) -> Section:
    """Parse an HTML fragment representing a numbered section.

    The extractor runs a single combined regex over the text to detect
    modalities (``must``, ``must not``, ``may``), conditional triggers
    (``if``, ``unless``, ``subject to``, ``despite``) and simple
    cross references (e.g. ``s 5B``, ``this Part``).
    """

    text = _strip_tags(html)

    heading_match = HEADING_RE.match(text)
    number: Optional[str] = None
    heading: Optional[str] = None
    if heading_match:
        number = heading_match.group("number")
        heading = heading_match.group("heading")

    modality: Optional[str] = None
    conditions: List[str] = []
    references: List[str] = []

    for match in TOKEN_RE.finditer(text):
        token = match.group().strip()
        group = match.lastgroup
        if group == "modality" and modality is None:
            modality = token.lower()
        elif group == "condition":
            conditions.append(token.lower())
        elif group == "xref":
            references.append(token)

    return Section(
        number=number,
        heading=heading,
        text=text,
        modality=modality,
        conditions=conditions,
        references=references,
    )


def fetch_section(html: str) -> Dict[str, object]:
    """Parse *html* and return raw text together with extracted rule metadata."""
    section = parse_html_section(html)
    return section.to_dict()
