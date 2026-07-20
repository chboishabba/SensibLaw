"""Legacy compatibility projection for the canonical section parser.

Parsing, rule extraction, and structural-node construction live in
``src.ingestion.section_parser``. This module retains the historical
``Provision`` and simple-section output shapes for callers that still import
``src.section_parser``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from src.ingestion.section_parser import (
    LogicTokenClass,
    ParsedNode,
    annotate_logic_tokens,
    parse_canonical_section,
    parse_html_section as _parse_html_section,
    parse_sections as _parse_sections,
)
from src.models.provision import Provision, RuleReference


@dataclass
class Section:
    """Historical simple projection of one canonical parsed section."""

    number: Optional[str]
    heading: Optional[str]
    text: str
    modality: Optional[str]
    conditions: list[str]
    references: list[str]

    def to_dict(self) -> dict[str, object]:
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


def _legacy_reference(reference: object) -> str:
    if isinstance(reference, RuleReference):
        return reference.citation_text or ""
    return str(reference)


def _legacy_rule_tokens(rule_tokens: dict[str, Any]) -> dict[str, object]:
    return {
        "modality": rule_tokens.get("modality"),
        "conditions": list(rule_tokens.get("conditions", [])),
        "references": [
            value
            for value in (
                _legacy_reference(reference)
                for reference in rule_tokens.get("references", [])
            )
            if value
        ],
    }


def _project_provision(node: ParsedNode) -> Provision:
    provision = Provision(
        text=node.text,
        identifier=node.identifier,
        heading=node.heading,
        node_type=node.node_type,
        rule_tokens=_legacy_rule_tokens(node.rule_tokens),
    )
    provision.children = [_project_provision(child) for child in node.children]
    return provision


def parse_sections(text: str) -> list[Provision]:
    """Return the historical ``Provision`` projection of canonical parse nodes."""

    return [_project_provision(node) for node in _parse_sections(text)]


def parse_html_section(html: str) -> Section:
    """Return the historical simple projection of a canonical parsed section."""

    section = _parse_html_section(html)
    return Section(
        number=section.number,
        heading=section.heading,
        text=section.text,
        modality=section.modality,
        conditions=list(section.conditions),
        references=[
            value
            for value in (
                _legacy_reference(reference) for reference in section.references
            )
            if value
        ],
    )


def fetch_section(html: str) -> dict[str, object]:
    """Return the historical JSON projection of a canonical parsed section."""

    return parse_html_section(html).to_dict()


__all__ = [
    "LogicTokenClass",
    "Section",
    "annotate_logic_tokens",
    "fetch_section",
    "parse_canonical_section",
    "parse_html_section",
    "parse_sections",
]
