import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Sequence, Tuple

import spacy
from spacy.tokens import Doc, Token

from src.models.provision import RuleReference
from src.nlp.rules import (
    CONDITION_LABEL,
    MODALITY_LABEL,
    REFERENCE_LABEL,
    RuleMatchSummary,
    match_rules,
)

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

THIS_ACT_WORK = "this_act"


class LogicTokenClass(str, Enum):
    """Classification labels applied to logic-bearing tokens."""

    ACTOR = "ACTOR"
    ACTION = "ACTION"
    MODALITY = "MODALITY"
    CONDITION = "CONDITION"
    REFERENCE = "REFERENCE"
    SPACE = "SPACE"
    PUNCT = "PUNCT"
    JUNK = "JUNK"


_NLP = spacy.blank("en")

if not Token.has_extension("class_"):
    Token.set_extension("class_", default=None)


_RULE_CLASS_MAP: Dict[str, LogicTokenClass] = {
    MODALITY_LABEL: LogicTokenClass.MODALITY,
    CONDITION_LABEL: LogicTokenClass.CONDITION,
    REFERENCE_LABEL: LogicTokenClass.REFERENCE,
}


def _apply_rule_matches(doc: Doc, summary: RuleMatchSummary) -> None:
    for match in summary.matches:
        label = _RULE_CLASS_MAP.get(match.label)
        if label is None:
            continue
        for token in match.span(doc):
            if token.is_space:
                continue
            token._.class_ = label


def _label_reference_tokens(
    doc: Doc,
    matches: Sequence[Tuple[RuleReference, Tuple[int, int]]],
) -> None:
    for _ref, (start_char, end_char) in matches:
        for token in doc:
            token_start = token.idx
            token_end = token.idx + len(token)
            if token_end <= start_char or token_start >= end_char:
                continue
            if token.is_space:
                continue
            token._.class_ = LogicTokenClass.REFERENCE


def _prepare_logic_doc(
    text: str,
    *,
    reference_matches: Optional[Sequence[Tuple[RuleReference, Tuple[int, int]]]] = None,
) -> Tuple[Doc, RuleMatchSummary, Sequence[Tuple[RuleReference, Tuple[int, int]]]]:
    doc = _NLP(text)
    for token in doc:
        token._.class_ = LogicTokenClass.SPACE if token.is_space else None

    summary = match_rules(doc)
    _apply_rule_matches(doc, summary)

    if reference_matches is None:
        reference_matches = _extract_reference_matches(text)

    _label_reference_tokens(doc, reference_matches)
    return doc, summary, reference_matches


def _finalise_logic_doc(doc: Doc) -> Doc:
    _expand_condition_scopes(doc)
    _label_actor_and_action(doc)
    _finalise_token_classes(doc)
    _verify_full_coverage(doc)
    return doc


def _expand_condition_scopes(doc: Doc) -> None:
    indices = [i for i, token in enumerate(doc) if token._.class_ == LogicTokenClass.CONDITION]
    for index in indices:
        position = index + 1
        while position < len(doc):
            token = doc[position]
            if token._.class_ in {LogicTokenClass.MODALITY, LogicTokenClass.CONDITION}:
                break
            if token._.class_ == LogicTokenClass.REFERENCE:
                break
            if token.is_punct:
                if token._.class_ is None:
                    token._.class_ = LogicTokenClass.PUNCT
                break
            if token.is_space:
                position += 1
                continue
            if token._.class_ is None:
                token._.class_ = LogicTokenClass.CONDITION
            position += 1


def _label_actor_and_action(doc: Doc) -> None:
    modality_indices = [i for i, token in enumerate(doc) if token._.class_ == LogicTokenClass.MODALITY]
    if not modality_indices:
        return

    first_modality = modality_indices[0]
    last_modality = modality_indices[-1]

    for token in doc[:first_modality]:
        if token.is_space:
            continue
        if token._.class_ is None and token.is_alpha:
            token._.class_ = LogicTokenClass.ACTOR

    action_start = last_modality + 1
    action_end = len(doc)
    for idx in range(action_start, len(doc)):
        token = doc[idx]
        if token._.class_ in {LogicTokenClass.CONDITION, LogicTokenClass.REFERENCE}:
            action_end = idx
            break
        if token.is_punct:
            token._.class_ = LogicTokenClass.PUNCT
            action_end = idx
            break

    for token in doc[action_start:action_end]:
        if token.is_space:
            continue
        if token._.class_ is None:
            token._.class_ = (
                LogicTokenClass.ACTION if token.is_alpha else LogicTokenClass.JUNK
            )


def _finalise_token_classes(doc: Doc) -> None:
    for token in doc:
        if token._.class_ is not None:
            continue
        if token.is_space:
            token._.class_ = LogicTokenClass.SPACE
        elif token.is_punct:
            token._.class_ = LogicTokenClass.PUNCT
        else:
            token._.class_ = LogicTokenClass.JUNK


def _verify_full_coverage(doc: Doc) -> None:
    missing = [token.text for token in doc if token._.class_ is None]
    if missing:
        raise ValueError(f"Unlabelled tokens found: {missing}")


def _serialise_logic_tokens(doc: Doc) -> List[Dict[str, object]]:
    serialised: List[Dict[str, object]] = []
    for token in doc:
        if token.is_space:
            continue
        label = token._.class_
        if isinstance(label, LogicTokenClass):
            class_name = label.value
        elif label is None:
            class_name = None
        else:
            class_name = str(label)
        serialised.append(
            {
                "text": token.text,
                "start": token.idx,
                "end": token.idx + len(token),
                "class": class_name,
            }
        )
    return serialised


def annotate_logic_tokens(
    text: str,
    *,
    reference_matches: Optional[Sequence[Tuple[RuleReference, Tuple[int, int]]]] = None,
) -> Doc:
    """Annotate ``text`` with logic token classes and return the spaCy doc."""

    doc, _, reference_matches = _prepare_logic_doc(
        text, reference_matches=reference_matches
    )
    _finalise_logic_doc(doc)
    return doc


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


def _build_reference(
    kind: str,
    subject: Optional[str],
    label: Optional[str],
    target: Optional[str],
    original: str,
) -> RuleReference:
    normalized_label = _normalize_label(label)
    clean_target = _clean_identifier(target)

    work: Optional[str]
    subject_clean = _clean_identifier(subject)
    if kind in {"external", "statute"}:
        work = subject_clean
    elif subject_clean:
        if subject_clean.lower() == "this":
            work = THIS_ACT_WORK
        else:
            work = subject_clean
    else:
        work = THIS_ACT_WORK if kind in {"internal", "structure"} else None

    pinpoint: Optional[str] = None
    section: Optional[str] = None

    if normalized_label:
        section = normalized_label
        pinpoint = clean_target
    elif clean_target:
        pinpoint = clean_target

    return RuleReference(
        work=work,
        section=section,
        pinpoint=pinpoint,
        citation_text=original,
    )


def _extract_reference_matches(text: str) -> List[Tuple[RuleReference, Tuple[int, int]]]:
    matches: List[Tuple[RuleReference, Tuple[int, int]]] = []
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
        reference = _build_reference(
            kind,
            subject.strip() if subject else None,
            label,
            target,
            original,
        )
        matches.append((reference, span))

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

    deduped: List[Tuple[RuleReference, Tuple[int, int]]] = []
    seen: set[Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]] = set()
    for reference, span in matches:
        key = (
            reference.work.lower() if reference.work else None,
            reference.section.lower() if reference.section else None,
            reference.pinpoint.lower() if reference.pinpoint else None,
            reference.citation_text.lower() if reference.citation_text else None,
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append((reference, span))

    return deduped


def _extract_references(text: str) -> List[RuleReference]:
    return [reference for reference, _ in _extract_reference_matches(text)]


def _extract_rule_tokens(text: str) -> Dict[str, object]:
    doc, summary, reference_matches = _prepare_logic_doc(text)
    _finalise_logic_doc(doc)
    references = [ref for ref, _ in reference_matches]

    return {
        "modality": summary.primary_modality,
        "conditions": summary.conditions,
        "references": references,
        "token_classes": _serialise_logic_tokens(doc),
    }


def _empty_tokens() -> Dict[str, object]:
    return {
        "modality": None,
        "conditions": [],
        "references": [],
        "token_classes": [],
    }


@dataclass
class ParsedNode:
    """Structured representation of a legislative unit."""

    node_type: str
    identifier: Optional[str]
    heading: Optional[str] = None
    text: str = ""
    rule_tokens: Dict[str, object] = field(default_factory=_empty_tokens)
    references: List[RuleReference] = field(default_factory=list)
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
                "references": [
                    ref.to_dict() if hasattr(ref, "to_dict") else ref
                    for ref in self.rule_tokens.get("references", [])
                ],
                "token_classes": [
                    dict(token)
                    if isinstance(token, dict)
                    else token
                    for token in self.rule_tokens.get("token_classes", [])
                ],
            },
            "references": [ref.to_dict() for ref in self.references],
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
    references: List[RuleReference]
    token_classes: List[Dict[str, object]]

    def to_dict(self) -> Dict[str, object]:
        return {
            "number": self.number,
            "heading": self.heading,
            "text": self.text,
            "rules": {
                "modality": self.modality,
                "conditions": list(self.conditions),
                "references": [ref.to_dict() for ref in self.references],
                "token_classes": [dict(token) for token in self.token_classes],
            },
        }


def parse_html_section(html: str) -> Section:
    """Parse an HTML fragment representing a numbered section.

    The extractor applies the shared spaCy matcher to detect modalities
    (``must``, ``must not``, ``may``), conditional triggers (``if``,
    ``unless``, ``subject to``) and cross references ranging from
    intra-Act markers (``s 5B``, ``this Part``) to structural headings and
    external statute citations (e.g. ``Native Title Act 1993 (Cth) s 223``).
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
        token_classes=tokens["token_classes"],
    )


def fetch_section(html: str) -> Dict[str, object]:
    """Parse *html* and return raw text together with extracted rule metadata."""
    section = parse_html_section(html)
    return section.to_dict()


def _finalize_node(node: ParsedNode) -> None:
    node.text = " ".join(part for part in node._buffer if part).strip()
    node.rule_tokens = _extract_rule_tokens(node.text)
    node.references = [
        ref if isinstance(ref, RuleReference) else RuleReference(**ref)
        for ref in node.rule_tokens.get("references", [])
    ]
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
"""Compatibility re-export for :mod:`section_parser` without overriding new APIs."""

try:  # pragma: no cover - optional legacy dependency
    import section_parser as _legacy_section_parser  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - legacy module absent
    _legacy_section_parser = None
else:  # pragma: no cover - thin compatibility bridge
    legacy_exports = getattr(_legacy_section_parser, "__all__", [])
    for name in legacy_exports:
        if name not in globals():
            globals()[name] = getattr(_legacy_section_parser, name)
        if name not in __all__:
            __all__.append(name)
