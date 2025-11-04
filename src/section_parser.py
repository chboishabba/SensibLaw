import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import spacy

from models.provision import Provision
from src.nlp.rules import match_rules


_NLP = spacy.blank("en")

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
SUBDIVISION_RE = re.compile(
    r"^Subdivision(?:\s+(?P<number>[A-Za-z0-9]+))?(?:\s*(?:[-–:]\s*)?(?P<heading>.+))?$",
    re.IGNORECASE,
)
SUBSECTION_RE = re.compile(r"^\((?P<number>\d+)\)\s*(?P<text>.+)$")

def _strip_tags(html: str) -> str:
    """Remove simple HTML tags, returning the text content."""

    return re.sub(r"<[^>]+>", "", html).strip()


def _extract_rule_tokens(text: str) -> Dict[str, object]:
    doc = _NLP(text)
    summary = match_rules(doc)
    return {
        "modality": summary.primary_modality,
        "conditions": summary.conditions,
        "references": summary.references,
    }


def _empty_tokens() -> Dict[str, object]:
    return {"modality": None, "conditions": [], "references": []}


@dataclass
class _ParsedNode:
    """Structured representation of a legislative unit."""

    node_type: str
    identifier: Optional[str]
    heading: Optional[str] = None
    text: str = ""
    rule_tokens: Dict[str, object] = field(default_factory=_empty_tokens)
    children: List["_ParsedNode"] = field(default_factory=list)
    _buffer: List[str] = field(default_factory=list, repr=False)


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

    The extractor applies the shared spaCy matcher to detect
    modalities (``must``, ``must not``, ``may``), conditional markers
    (``if``, ``unless``, ``subject to``) and simple cross references
    (e.g. ``s 5B``, ``this Part``).
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


def _finalize_node(node: _ParsedNode) -> None:
    node.text = " ".join(part for part in node._buffer if part).strip()
    node.rule_tokens = _extract_rule_tokens(node.text)
    node._buffer.clear()
    for child in node.children:
        _finalize_node(child)


def _attach_node(
    collection: List[_ParsedNode],
    parent: Optional[_ParsedNode],
    node: _ParsedNode,
) -> _ParsedNode:
    target = parent.children if parent else collection
    target.append(node)
    return node


def _node_to_provision(node: _ParsedNode) -> Provision:
    provision = Provision(
        text=node.text,
        identifier=node.identifier,
        heading=node.heading,
        node_type=node.node_type,
        rule_tokens=dict(node.rule_tokens),
    )
    provision.children = [_node_to_provision(child) for child in node.children]
    return provision


def parse_sections(text: str) -> List[Provision]:
    """Parse free-form text into a hierarchy of :class:`Provision` instances."""

    nodes: List[_ParsedNode] = []
    current_part: Optional[_ParsedNode] = None
    current_division: Optional[_ParsedNode] = None
    current_section: Optional[_ParsedNode] = None
    current_subdivision: Optional[_ParsedNode] = None
    current_subsection: Optional[_ParsedNode] = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        part_match = PART_RE.match(line)
        if part_match:
            current_part = _ParsedNode(
                node_type="part",
                identifier=part_match.group("number"),
                heading=part_match.group("heading"),
            )
            _attach_node(nodes, None, current_part)
            current_division = None
            current_section = None
            current_subdivision = None
            current_subsection = None
            continue

        division_match = DIVISION_RE.match(line)
        if division_match:
            parent = current_part
            current_division = _ParsedNode(
                node_type="division",
                identifier=division_match.group("number"),
                heading=division_match.group("heading"),
            )
            _attach_node(nodes, parent, current_division)
            current_subdivision = None
            current_section = None
            current_subsection = None
            continue

        subdivision_match = SUBDIVISION_RE.match(line)
        if subdivision_match:
            parent = current_division or current_part
            current_subdivision = _ParsedNode(
                node_type="subdivision",
                identifier=subdivision_match.group("number"),
                heading=subdivision_match.group("heading"),
            )
            _attach_node(nodes, parent, current_subdivision)
            current_section = None
            current_subsection = None
            continue

        section_match = HEADING_RE.match(line)
        if section_match:
            parent = current_subdivision or current_division or current_part
            current_section = _ParsedNode(
                node_type="section",
                identifier=section_match.group("number"),
                heading=section_match.group("heading"),
            )
            _attach_node(nodes, parent, current_section)
            current_subsection = None
            continue

        subsection_match = SUBSECTION_RE.match(line)
        if subsection_match and current_section:
            current_subsection = _ParsedNode(
                node_type="subsection",
                identifier=f"({subsection_match.group('number')})",
            )
            current_subsection._buffer.append(subsection_match.group("text"))
            _attach_node(nodes, current_section, current_subsection)
            continue

        target = (
            current_subsection
            or current_section
            or current_subdivision
            or current_division
            or current_part
        )
        if target is None:
            target = _ParsedNode(node_type="section", identifier=None)
            _attach_node(nodes, None, target)
            current_part = None
            current_division = None
            current_section = target
            current_subdivision = None
            current_subsection = None

        target._buffer.append(line)

    for node in nodes:
        _finalize_node(node)

    return [_node_to_provision(node) for node in nodes]


__all__ = ["parse_sections", "parse_html_section", "fetch_section", "Section"]
