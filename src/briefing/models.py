"""Data models for the brief preparation pack."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Mapping, Optional


# ---------------------------------------------------------------------------
# Matter-side models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IssueProfile:
    """High-level description of an issue in dispute."""

    issue: str
    statement: str = ""

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "IssueProfile":
        return cls(
            issue=str(data.get("issue", "")), statement=str(data.get("statement", ""))
        )


@dataclass(frozen=True)
class MatterExhibit:
    """Representation of an evidentiary exhibit."""

    id: str
    description: str
    source: str
    annexed: bool = True
    pages: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "MatterExhibit":
        return cls(
            id=str(data.get("id", "")),
            description=str(data.get("description", "")),
            source=str(data.get("source", "")),
            annexed=bool(data.get("annexed", True)),
            pages=str(data.get("pages")) if data.get("pages") is not None else None,
        )


@dataclass(frozen=True)
class MatterAuthority:
    """Authority relied on for one or more factors."""

    id: str
    issue: str
    name: str
    citation: str
    pin_cite: Optional[str] = None
    anchors: List[str] = field(default_factory=list)
    proposition: str = ""

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "MatterAuthority":
        return cls(
            id=str(data.get("id", "")),
            issue=str(data.get("issue", "")),
            name=str(data.get("name", "")),
            citation=str(data.get("citation", "")),
            pin_cite=str(data.get("pin_cite"))
            if data.get("pin_cite") is not None
            else None,
            anchors=[str(a) for a in data.get("anchors", [])],
            proposition=str(data.get("proposition", "")),
        )


@dataclass(frozen=True)
class MatterFactor:
    """Factor asserted in support of relief."""

    id: str
    issue: str
    section: str
    proposition: str
    assertion: str
    exhibits: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "MatterFactor":
        return cls(
            id=str(data.get("id", "")),
            issue=str(data.get("issue", "")),
            section=str(data.get("section", "")),
            proposition=str(data.get("proposition", "")),
            assertion=str(data.get("assertion", "")),
            exhibits=[str(e) for e in data.get("exhibits", [])],
        )


@dataclass(frozen=True)
class MatterProfile:
    """Container for all matter inputs required for the brief pack."""

    title: str
    issues: List[IssueProfile]
    factors: List[MatterFactor]
    authorities: List[MatterAuthority]
    exhibits: List[MatterExhibit]

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "MatterProfile":
        return cls(
            title=str(data.get("title", "")),
            issues=[IssueProfile.from_dict(item) for item in data.get("issues", [])],
            factors=[MatterFactor.from_dict(item) for item in data.get("factors", [])],
            authorities=[
                MatterAuthority.from_dict(item) for item in data.get("authorities", [])
            ],
            exhibits=[
                MatterExhibit.from_dict(item) for item in data.get("exhibits", [])
            ],
        )

    def factors_for_issue(self, issue: str) -> List[MatterFactor]:
        return [factor for factor in self.factors if factor.issue == issue]

    def authorities_for_factor(self, factor_id: str) -> List[MatterAuthority]:
        return [
            authority
            for authority in self.authorities
            if factor_id in authority.anchors
        ]

    def exhibit_map(self) -> Dict[str, MatterExhibit]:
        return {exhibit.id: exhibit for exhibit in self.exhibits}


# ---------------------------------------------------------------------------
# Output-side models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AuthoritySlot:
    """Authority placeholder for a submission section."""

    name: str
    citation: str
    pin_cite: Optional[str]
    anchor: str
    proposition: str = ""

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "citation": self.citation,
            "pin_cite": self.pin_cite,
            "anchor": self.anchor,
            "proposition": self.proposition,
        }


@dataclass(frozen=True)
class SkeletonSection:
    """One section within the submission skeleton."""

    heading: str
    anchors: List[str]
    authorities: List[AuthoritySlot]

    def to_dict(self) -> Dict[str, object]:
        return {
            "heading": self.heading,
            "anchors": list(self.anchors),
            "authorities": [slot.to_dict() for slot in self.authorities],
        }


@dataclass(frozen=True)
class IssueSkeleton:
    """Skeleton for a specific issue (e.g., parenting or property)."""

    issue: str
    sections: List[SkeletonSection]

    def to_dict(self) -> Dict[str, object]:
        return {
            "issue": self.issue,
            "sections": [section.to_dict() for section in self.sections],
        }


@dataclass(frozen=True)
class CoverageRow:
    """Row in the factor coverage grid."""

    factor_id: str
    issue: str
    section: str
    proposition: str
    status: str
    exhibits: List[str]
    missing: List[str]

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class CoverageGrid:
    """Grid describing coverage status for each factor."""

    rows: List[CoverageRow]

    def to_dict(self) -> Dict[str, object]:
        return {"rows": [row.to_dict() for row in self.rows]}


@dataclass(frozen=True)
class CounterEvidence:
    """Evidence reference used to answer a counter-argument."""

    exhibit_id: str
    description: str

    def to_dict(self) -> Dict[str, str]:
        return {"exhibit_id": self.exhibit_id, "description": self.description}


@dataclass(frozen=True)
class CounterArgument:
    """Predictable pushback and the planned response."""

    title: str
    pushback: str
    response: str
    evidence: List[CounterEvidence]

    def to_dict(self) -> Dict[str, object]:
        return {
            "title": self.title,
            "pushback": self.pushback,
            "response": self.response,
            "evidence": [item.to_dict() for item in self.evidence],
        }


@dataclass(frozen=True)
class BundleIssue:
    """Problem encountered while checking the bundle."""

    exhibit_id: str
    reason: str
    details: str

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class BundleReport:
    """Outcome from running the bundle checker."""

    missing_annexures: List[BundleIssue]
    unreferenced_exhibits: List[str]

    def to_dict(self) -> Dict[str, object]:
        return {
            "missing_annexures": [issue.to_dict() for issue in self.missing_annexures],
            "unreferenced_exhibits": list(self.unreferenced_exhibits),
        }


@dataclass(frozen=True)
class BriefPack:
    """Complete bundle of outputs for counsel."""

    submission_skeletons: Dict[str, IssueSkeleton]
    coverage_grid: CoverageGrid
    counter_arguments: Dict[str, List[CounterArgument]]
    bundle_report: BundleReport
    first_cut_brief: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "submission_skeletons": {
                issue: skeleton.to_dict()
                for issue, skeleton in self.submission_skeletons.items()
            },
            "coverage_grid": self.coverage_grid.to_dict(),
            "counter_arguments": {
                factor_id: [item.to_dict() for item in items]
                for factor_id, items in self.counter_arguments.items()
            },
            "bundle_report": self.bundle_report.to_dict(),
            "first_cut_brief": self.first_cut_brief,
        }


__all__ = [
    "AuthoritySlot",
    "BriefPack",
    "BundleIssue",
    "BundleReport",
    "CounterArgument",
    "CounterEvidence",
    "CoverageGrid",
    "CoverageRow",
    "IssueProfile",
    "IssueSkeleton",
    "MatterAuthority",
    "MatterExhibit",
    "MatterFactor",
    "MatterProfile",
    "SkeletonSection",
]
