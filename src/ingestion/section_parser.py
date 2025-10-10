import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# Precompiled regex to capture leading numbering/heading from a block of text
HEADING_RE = re.compile(r"^(?P<number>\d+(?:\.\d+)*)\s+(?P<heading>.+)$")

PART_RE = re.compile(
    r"^Part\s+(?P<number>[A-Z0-9IVXLC]+)(?:\s*(?:[-–:]\s*)?(?P<heading>.+))?$",
    re.IGNORECASE,
)
DIVISION_RE = re.compile(
    r"^Division\s+(?P<number>[A-Za-z0-9]+)(?:\s*(?:[-–:]\s*)?(?P<heading>.+))?$",
    re.IGNORECASE,
)
SUBSECTION_RE = re.compile(r"^\((?P<number>\d+)\)\s*(?P<text>.+)$")
NOTE_RE = re.compile(r"^(Note|Notes|Example|Penalty)\b", re.IGNORECASE)

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


def _extract_rule_tokens(text: str) -> Dict[str, object]:
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

    return {"modality": modality, "conditions": conditions, "references": references}


def _empty_tokens() -> Dict[str, object]:
    return {"modality": None, "conditions": [], "references": []}


@dataclass
class ParsedNode:
    """Structured representation of a legislative unit."""

    node_type: str
    identifier: Optional[str]
    heading: Optional[str] = None
    text: str = ""
    rule_tokens: Dict[str, object] = field(default_factory=_empty_tokens)
    children: List["ParsedNode"] = field(default_factory=list)
    _buffer: List[str] = field(default_factory=list, repr=False)

    def to_dict(self) -> Dict[str, object]:
        return {
            "type": self.node_type,
            "identifier": self.identifier,
            "heading": self.heading,
            "text": self.text,
            "rule_tokens": {
                "modality": self.rule_tokens.get("modality"),
                "conditions": list(self.rule_tokens.get("conditions", [])),
                "references": list(self.rule_tokens.get("references", [])),
            },
            "children": [child.to_dict() for child in self.children],
        }


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

    tokens = _extract_rule_tokens(text)

    return Section(
        number=number,
        heading=heading,
        text=text,
        modality=tokens["modality"],
        conditions=tokens["conditions"],
        references=tokens["references"],
    )


def fetch_section(html: str) -> Dict[str, object]:
    """Parse *html* and return raw text together with extracted rule metadata."""
    section = parse_html_section(html)
    return section.to_dict()


def _finalize_node(node: ParsedNode) -> None:
    node.text = " ".join(part for part in node._buffer if part).strip()
    node.rule_tokens = _extract_rule_tokens(node.text)
    node._buffer.clear()
    for child in node.children:
        _finalize_node(child)


def _attach_node(
    collection: List[ParsedNode],
    parent: Optional[ParsedNode],
    node: ParsedNode,
) -> ParsedNode:
    target = parent.children if parent else collection
    target.append(node)
    return node


def parse_sections(text: str) -> List[ParsedNode]:
    """Parse free-form text into a hierarchy of structured nodes."""

    nodes: List[ParsedNode] = []
    current_part: Optional[ParsedNode] = None
    current_division: Optional[ParsedNode] = None
    current_section: Optional[ParsedNode] = None
    current_subsection: Optional[ParsedNode] = None

    last_line_was_blank = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            last_line_was_blank = True
            continue

        blank_preceded = last_line_was_blank
        last_line_was_blank = False

        part_match = PART_RE.match(line)
        if part_match:
            current_part = ParsedNode(
                node_type="part",
                identifier=part_match.group("number"),
                heading=part_match.group("heading"),
            )
            _attach_node(nodes, None, current_part)
            current_division = None
            current_section = None
            current_subsection = None
            continue

        division_match = DIVISION_RE.match(line)
        if division_match:
            parent = current_part
            current_division = ParsedNode(
                node_type="division",
                identifier=division_match.group("number"),
                heading=division_match.group("heading"),
            )
            _attach_node(nodes, parent, current_division)
            current_section = None
            current_subsection = None
            continue

        section_match = HEADING_RE.match(line)
        if section_match:
            parent = current_division or current_part
            current_section = ParsedNode(
                node_type="section",
                identifier=section_match.group("number"),
                heading=section_match.group("heading"),
            )
            _attach_node(nodes, parent, current_section)
            current_subsection = None
            continue

        subsection_match = SUBSECTION_RE.match(line)
        if subsection_match and current_section:
            current_subsection = ParsedNode(
                node_type="subsection",
                identifier=f"({subsection_match.group('number')})",
            )
            current_subsection._buffer.append(subsection_match.group("text"))
            _attach_node(nodes, current_section, current_subsection)
            continue

        if current_subsection and (blank_preceded or NOTE_RE.match(line)):
            current_subsection = None

        target = current_subsection or current_section or current_division or current_part
        if target is None:
            target = ParsedNode(node_type="section", identifier=None)
            _attach_node(nodes, None, target)
            current_part = None
            current_division = None
            current_section = target
            current_subsection = None

        target._buffer.append(line)

    for node in nodes:
        _finalize_node(node)

    return nodes


__all__ = ["ParsedNode", "parse_sections", "parse_html_section", "fetch_section"]
