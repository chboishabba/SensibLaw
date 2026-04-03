from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable


@dataclass(frozen=True)
class StandardsReference:
    reference_id: str
    title: str
    issuing_body: str
    assertiveness: str
    scope_notes: str
    jurisdiction_hint: str
    document_url: str
    canonical_query_keys: tuple[str, ...]
    applicability: tuple[str, ...]
    language: str = "en"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def build_metadata(self, focus: str) -> dict[str, object]:
        return {
            "reference_id": self.reference_id,
            "focus": focus,
            "issuing_body": self.issuing_body,
            "assertiveness": self.assertiveness,
            "scope_notes": self.scope_notes,
            "jurisdiction_hint": self.jurisdiction_hint,
            "document_url": self.document_url,
            "canonical_query_keys": list(self.canonical_query_keys),
            "applicability": list(self.applicability),
            "language": self.language,
        }


def canonical_standards_references() -> list[StandardsReference]:
    return [
        StandardsReference(
            reference_id="iso_iec_27001",
            title="ISO/IEC 27001: Information Security Management",
            issuing_body="ISO/IEC",
            assertiveness="non-binding best practice",
            scope_notes="Provides requirements for establishing, maintaining and improving an information security management system.",
            jurisdiction_hint="global",
            document_url="https://www.iso.org/standard/27001.html",
            canonical_query_keys=("clause", "control"),
            applicability=("information security", "governance"),
        ),
        StandardsReference(
            reference_id="iso_iec_31000",
            title="ISO/IEC 31000: Risk Management",
            issuing_body="ISO",
            assertiveness="guidance/reference",
            scope_notes="Framework for risk management that complements country-specific legal frameworks.",
            jurisdiction_hint="global",
            document_url="https://www.iso.org/iso-31000-risk-management.html",
            canonical_query_keys=("principle", "process"),
            applicability=("risk", "compliance"),
        ),
        StandardsReference(
            reference_id="iec_61131",
            title="IEC 61131-3: Programmable Controllers",
            issuing_body="IEC",
            assertiveness="technical norm",
            scope_notes="Defines PLC programming languages commonly referenced in industrial safety law.",
            jurisdiction_hint="technical",
            document_url="https://webstore.iec.ch/publication/3288",
            canonical_query_keys=("part", "section"),
            applicability=("industrial automation", "safety"),
        ),
    ]


def canonical_standards_metadata(focus: str) -> list[dict[str, object]]:
    return [ref.build_metadata(focus) for ref in canonical_standards_references()]
