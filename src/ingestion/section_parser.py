import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

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

# Single-pass combined regex mimicking an Aho–Corasick matcher for keywords
TOKEN_RE = re.compile(
    r"(?P<modality>must not|must|may)|"
    r"(?P<condition>if|unless|subject to|despite)",
    re.IGNORECASE,
)

INTERNAL_REF_RE = re.compile(
    r"\b(?P<label>s|ss|section|sections|regulation|regulations|rule|rules)\s+"
    r"(?P<target>\d+[A-Za-z]*(?:\([^\)]+\))?(?:\s*(?:and|to|[-–])\s*\d+[A-Za-z]*(?:\([^\)]+\))?)?)",
    re.IGNORECASE,
)

STRUCTURE_REF_RE = re.compile(
    r"\b(?P<label>Part|Division|Chapter|Schedule)\s+"
    r"(?P<identifier>[A-Z0-9IVXLC]+(?:\.\d+)?)",
    re.IGNORECASE,
)

SELF_REF_RE = re.compile(
    r"\bthis\s+(?P<label>Act|Part|Division|Chapter|Schedule)\b",
    re.IGNORECASE,
)

EXTERNAL_STATUTE_RE = re.compile(
    r"(?P<act>"
    r"(?:(?:(?-i:[A-Z])[A-Za-z'&-]*)|\([^)]+\))(?:\s+(?:(?:(?-i:[A-Z])[A-Za-z'&-]*)|\([^)]+\)))*\s+"
    r"(?i:(?:Act|Ordinance|Regulation|Regulations|Code))\s+\d{4}(?:\s*\([A-Za-z]+\))?)"
    r"(?:\s+(?P<section_label>(?i:s|ss|section|sections|part|division|chapter|schedule))\s+"
    r"(?P<section_id>\d+[A-Za-z]*(?:\([^\)]+\))?(?:\s*(?:and|to|[-–])\s*\d+[A-Za-z]*(?:\([^\)]+\))?)?))?",
)

ReferenceTuple = Tuple[str, Optional[str], Optional[str], Optional[str], str]


def _strip_tags(html: str) -> str:
    """Remove simple HTML tags, returning the text content."""
    return re.sub(r"<[^>]+>", "", html).strip()


def _normalize_label(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None
    lowered = raw.strip().lower()
    mapping = {
        "s": "section",
        "ss": "sections",
    }
    return mapping.get(lowered, lowered)


def _clean_identifier(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None
    return re.sub(r"\s+", " ", raw.strip()) or None


def _extract_references(text: str) -> List[ReferenceTuple]:
    references: List[ReferenceTuple] = []
    spans: List[Tuple[int, int]] = []

    def overlaps(span: Tuple[int, int]) -> bool:
        for start, end in spans:
            if not (span[1] <= start or span[0] >= end):
                return True
        return False

    def add_reference(
        kind: str,
        subject: Optional[str],
        label: Optional[str],
        target: Optional[str],
        match: re.Match[str],
    ) -> None:
        span = match.span()
        if overlaps(span):
            return
        original = text[span[0] : span[1]].strip()
        if not original:
            return
        spans.append(span)
        references.append(
            (
                kind,
                subject.strip() if subject else None,
                _normalize_label(label),
                _clean_identifier(target),
                original,
            )
        )

    for match in EXTERNAL_STATUTE_RE.finditer(text):
        act = match.group("act")
        label = match.group("section_label")
        section_id = match.group("section_id")
        kind = "external" if label else "statute"
        add_reference(kind, act, label, section_id, match)

    for match in STRUCTURE_REF_RE.finditer(text):
        add_reference(
            "structure", None, match.group("label"), match.group("identifier"), match
        )

    for match in INTERNAL_REF_RE.finditer(text):
        add_reference(
            "internal", None, match.group("label"), match.group("target"), match
        )

    for match in SELF_REF_RE.finditer(text):
        add_reference("internal", "this", match.group("label"), None, match)

    return references


def _extract_rule_tokens(text: str) -> Dict[str, object]:
    modality: Optional[str] = None
    conditions: List[str] = []
    references: List[ReferenceTuple] = []
    seen_conditions: set[str] = set()

    for match in TOKEN_RE.finditer(text):
        token = match.group().strip()
        group = match.lastgroup
        if group == "modality" and modality is None:
            modality = token.lower()
        elif group == "condition":
            lowered = token.lower()
            if lowered not in seen_conditions:
                seen_conditions.add(lowered)
                conditions.append(lowered)

    references.extend(_extract_references(text))
    deduped_refs: List[ReferenceTuple] = []
    seen_refs: set[
        tuple[Optional[str], Optional[str], Optional[str], Optional[str]]
    ] = set()
    for ref in references:
        kind, subject, label, target, original = ref
        key = (
            kind.lower() if kind else None,
            subject.lower() if subject else None,
            label.lower() if label else None,
            target.lower() if target else None,
        )
        if key in seen_refs:
            continue
        seen_refs.add(key)
        deduped_refs.append(ref)

    return {
        "modality": modality,
        "conditions": conditions,
        "references": deduped_refs,
    }


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
    references: List[ReferenceTuple] = field(default_factory=list)
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
            "references": list(self.references),
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
    references: List[ReferenceTuple]

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
    (``if``, ``unless``, ``subject to``, ``despite``) and cross references
    ranging from intra-Act markers (``s 5B``, ``this Part``) to structural
    headings and external statute citations (e.g. ``Native Title Act 1993 (Cth)
    s 223``).
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
    node.references = list(node.rule_tokens.get("references", []))
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
    current_subdivision: Optional[ParsedNode] = None
    current_subsection: Optional[ParsedNode] = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

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
            current_subdivision = None
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
            current_subdivision = None
            current_section = None
            current_subsection = None
            continue

        subdivision_match = SUBDIVISION_RE.match(line)
        if subdivision_match:
            parent = current_division or current_part
            current_subdivision = ParsedNode(
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

        target = (
            current_subsection
            or current_section
            or current_subdivision
            or current_division
            or current_part
        )
        if target is None:
            target = ParsedNode(node_type="section", identifier=None)
            _attach_node(nodes, None, target)
            current_part = None
            current_division = None
            current_section = target
            current_subdivision = None
            current_subsection = None

        target._buffer.append(line)

    for node in nodes:
        _finalize_node(node)

    return nodes


__all__ = ["ParsedNode", "parse_sections", "parse_html_section", "fetch_section"]
"""Compatibility re-export for :mod:`src.section_parser`."""

from ..section_parser import *  # noqa: F401,F403
