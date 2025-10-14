"""Builder for the brief preparation pack."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping

from .models import (
    AuthoritySlot,
    BriefPack,
    BundleIssue,
    BundleReport,
    CounterArgument,
    CounterEvidence,
    CoverageGrid,
    CoverageRow,
    IssueSkeleton,
    MatterAuthority,
    MatterExhibit,
    MatterFactor,
    MatterProfile,
    SkeletonSection,
)

_COUNTER_TEMPLATES: List[Mapping[str, str]] = [
    {
        "title": "Credibility challenge",
        "pushback": "Opponent will say {proposition} is overstated because {assertion} comes from the client.",
        "response": "Anchor back to {primary_evidence} and highlight consistent reporting across the file.",
    },
    {
        "title": "Statutory threshold",
        "pushback": "Expect a submission that {section} is not engaged on these facts.",
        "response": "Walk the Bench through {authority_label} and tie it to {primary_evidence}.",
    },
    {
        "title": "Weight attack",
        "pushback": "Anticipate an argument that any {issue} relief should be minimal because the material is thin.",
        "response": "Direct attention to the documentary trail: {evidence_list}.",
    },
]


@dataclass(slots=True)
class _FactorContext:
    factor: MatterFactor
    exhibits: List[MatterExhibit]
    missing_references: List[str]
    authorities: List[MatterAuthority]


class BriefPackBuilder:
    """Construct the solicitor-to-counsel preparation pack."""

    def __init__(self, *, counter_limit: int = 3) -> None:
        self.counter_limit = counter_limit

    def build(self, matter: MatterProfile) -> BriefPack:
        """Build the full brief pack for *matter*."""

        exhibit_map = matter.exhibit_map()
        factor_contexts = {
            factor.id: self._build_factor_context(factor, matter, exhibit_map)
            for factor in matter.factors
        }
        skeletons = self._build_submission_skeletons(matter, factor_contexts)
        coverage = self._build_coverage_grid(factor_contexts)
        counters = self._build_counter_arguments(factor_contexts)
        bundle = self._build_bundle_report(factor_contexts, matter.exhibits)
        first_cut = self._build_first_cut_brief(matter, skeletons, factor_contexts)
        return BriefPack(
            submission_skeletons=skeletons,
            coverage_grid=coverage,
            counter_arguments=counters,
            bundle_report=bundle,
            first_cut_brief=first_cut,
        )

    def _build_factor_context(
        self,
        factor: MatterFactor,
        matter: MatterProfile,
        exhibits: Mapping[str, MatterExhibit],
    ) -> _FactorContext:
        linked: List[MatterExhibit] = []
        missing: List[str] = []
        for exhibit_id in factor.exhibits:
            exhibit = exhibits.get(exhibit_id)
            if exhibit is None:
                missing.append(exhibit_id)
            else:
                linked.append(exhibit)
        authorities = matter.authorities_for_factor(factor.id)
        return _FactorContext(
            factor=factor,
            exhibits=linked,
            missing_references=missing,
            authorities=authorities,
        )

    def _build_submission_skeletons(
        self,
        matter: MatterProfile,
        contexts: Mapping[str, _FactorContext],
    ) -> Dict[str, IssueSkeleton]:
        skeletons: Dict[str, IssueSkeleton] = {}
        for issue in matter.issues:
            sections: List[SkeletonSection] = []
            for factor in matter.factors_for_issue(issue.issue):
                context = contexts[factor.id]
                authorities = context.authorities or [
                    MatterAuthority(
                        id=f"placeholder::{factor.id}",
                        issue=issue.issue,
                        name="Authority to be confirmed",
                        citation="",
                        pin_cite=None,
                        anchors=[factor.id],
                        proposition="",
                    )
                ]
                slots = [
                    AuthoritySlot(
                        name=authority.name,
                        citation=authority.citation,
                        pin_cite=authority.pin_cite,
                        anchor=factor.id,
                        proposition=authority.proposition,
                    )
                    for authority in authorities
                ]
                anchors = [factor.id]
                anchors.extend(exhibit.id for exhibit in context.exhibits)
                heading = f"{factor.section} – {factor.proposition}"
                sections.append(
                    SkeletonSection(
                        heading=heading,
                        anchors=anchors,
                        authorities=slots,
                    )
                )
            skeletons[issue.issue] = IssueSkeleton(issue=issue.issue, sections=sections)
        return skeletons

    def _build_coverage_grid(
        self, contexts: Mapping[str, _FactorContext]
    ) -> CoverageGrid:
        rows: List[CoverageRow] = []
        for context in contexts.values():
            factor = context.factor
            annexed = [ex for ex in context.exhibits if ex.annexed]
            if annexed:
                status = "supported"
            elif context.exhibits or context.missing_references:
                status = "thin"
            else:
                status = "unsupported"
            row = CoverageRow(
                factor_id=factor.id,
                issue=factor.issue,
                section=factor.section,
                proposition=factor.proposition,
                status=status,
                exhibits=[ex.id for ex in context.exhibits],
                missing=list(context.missing_references),
            )
            rows.append(row)
        rows.sort(key=lambda row: (row.issue, row.section, row.factor_id))
        return CoverageGrid(rows=rows)

    def _build_counter_arguments(
        self, contexts: Mapping[str, _FactorContext]
    ) -> Dict[str, List[CounterArgument]]:
        output: Dict[str, List[CounterArgument]] = {}
        for factor_id, context in contexts.items():
            factor = context.factor
            annexed = [ex for ex in context.exhibits if ex.annexed]
            primary = (
                annexed[0]
                if annexed
                else (context.exhibits[0] if context.exhibits else None)
            )
            primary_evidence = (
                f"{primary.id}: {primary.description}"
                if primary
                else "identify exhibit"
            )
            authority = context.authorities[0] if context.authorities else None
            authority_label = (
                f"{authority.name} ({authority.citation})"
                if authority
                else "leading authority"
            )
            evidence_list = (
                ", ".join(f"{ex.id}: {ex.description}" for ex in context.exhibits)
                or "no exhibits on file"
            )
            evidences = [
                CounterEvidence(exhibit_id=ex.id, description=ex.description)
                for ex in context.exhibits
            ]
            arguments: List[CounterArgument] = []
            for template in _COUNTER_TEMPLATES[: self.counter_limit]:
                pushback = template["pushback"].format(
                    proposition=factor.proposition,
                    assertion=factor.assertion,
                    section=factor.section,
                    issue=factor.issue,
                )
                response = template["response"].format(
                    primary_evidence=primary_evidence,
                    authority_label=authority_label,
                    evidence_list=evidence_list,
                )
                arguments.append(
                    CounterArgument(
                        title=template["title"],
                        pushback=pushback,
                        response=response,
                        evidence=evidences,
                    )
                )
            output[factor_id] = arguments
        return output

    def _build_bundle_report(
        self,
        contexts: Mapping[str, _FactorContext],
        exhibits: Iterable[MatterExhibit],
    ) -> BundleReport:
        missing: List[BundleIssue] = []
        referenced_ids: set[str] = set()
        for context in contexts.values():
            factor = context.factor
            referenced_ids.update(ex.id for ex in context.exhibits)
            for missing_id in context.missing_references:
                missing.append(
                    BundleIssue(
                        exhibit_id=missing_id,
                        reason="missing",
                        details=f"Referenced by factor {factor.id} but not provided",
                    )
                )
            for exhibit in context.exhibits:
                if not exhibit.annexed:
                    missing.append(
                        BundleIssue(
                            exhibit_id=exhibit.id,
                            reason="not_annexed",
                            details=f"Factor {factor.id} references exhibit not annexed to bundle",
                        )
                    )
        all_ids = {exhibit.id for exhibit in exhibits}
        unreferenced = sorted(all_ids - referenced_ids)
        missing.sort(key=lambda issue: (issue.reason, issue.exhibit_id))
        return BundleReport(
            missing_annexures=missing, unreferenced_exhibits=unreferenced
        )

    def _build_first_cut_brief(
        self,
        matter: MatterProfile,
        skeletons: Mapping[str, IssueSkeleton],
        contexts: Mapping[str, _FactorContext],
    ) -> str:
        exhibit_map = matter.exhibit_map()
        lines: List[str] = []
        if matter.title:
            lines.append(matter.title)
            lines.append("")
        for issue in matter.issues:
            skeleton = skeletons.get(issue.issue)
            if skeleton is None:
                continue
            lines.append(f"Issue: {issue.issue.title()}")
            if issue.statement:
                lines.append(f"Objective: {issue.statement}")
            for section in skeleton.sections:
                lines.append(f"- {section.heading}")
                for slot in section.authorities:
                    pin = f" at {slot.pin_cite}" if slot.pin_cite else ""
                    proposition = f" – {slot.proposition}" if slot.proposition else ""
                    lines.append(
                        f"    Authority: {slot.name} ({slot.citation}){pin}{proposition}"
                    )
                linked_exhibits = [
                    f"{exhibit_id}: {exhibit_map[exhibit_id].description}"
                    for exhibit_id in section.anchors[1:]
                    if exhibit_id in exhibit_map
                ]
                if linked_exhibits:
                    lines.append(f"    Evidence: {', '.join(linked_exhibits)}")
                else:
                    lines.append("    Evidence: identify supporting exhibit")
                lines.append(f"    Anchors: {', '.join(section.anchors)}")
            lines.append("")
        return "\n".join(lines).strip()


__all__ = ["BriefPackBuilder", "BriefPack"]
