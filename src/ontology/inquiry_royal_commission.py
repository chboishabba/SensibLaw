"""Normalized scaffold for inquiry and royal commission reports."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Iterable


def inquiry_contract() -> dict[str, str | Iterable[str]]:
    return {
        "scope": "inquiry/royal commission advisory surface",
        "constraints": [
            "reports are marked as evidentiary/advisory, never binding authority",
            "links to legislation are tagged as influence paths, not authoritative enactments",
            "references to doctrine or policy proposals preserve provenance without promotion",
        ],
        "authority_signal": "derived-only advisory signal; downstream lanes treat uptake as optional",
        "justification": (
            "Keeps royal commission work distinct from statutory law while providing deterministic metadata for influence tracking."
        ),
    }


@dataclass(frozen=True)
class InquiryReport:
    report_id: str
    title: str
    jurisdiction: str
    issued_date: str
    summary: str
    advisory_tags: list[str]
    influence_targets: list[str]


def build_sample_inquiries() -> dict[str, InquiryReport]:
    reports = [
        InquiryReport(
            report_id="inquiry:aus:rcs:2009:banking",
            title="Australian Banking Royal Commission Final Report",
            jurisdiction="Australia",
            issued_date="2019-02-01",
            summary="Detailed misconduct findings with recommendations for enhanced consumer protections.",
            advisory_tags=["consumer_protection", "banking_legislation", "executive_power"],
            influence_targets=["law:aus:consumer_credit", "policy:aus:banking_supervision"],
        ),
        InquiryReport(
            report_id="inquiry:uk:rcs:2015:child_protection",
            title="UK Child Protection Inquiry",
            jurisdiction="United Kingdom",
            issued_date="2015-12-15",
            summary="Examined systemic child protection failures and proposed statutory reforms.",
            advisory_tags=["child_welfare", "statutory_reform"],
            influence_targets=["law:uk:children_act", "policy:uk:local_authority_responsibility"],
        ),
        InquiryReport(
            report_id="inquiry:ca:commission:2020:healthcare",
            title="Canadian Healthcare Inquiry",
            jurisdiction="Canada",
            issued_date="2020-08-30",
            summary="Advised on pandemic preparedness and provincial/federal coordination mechanisms.",
            advisory_tags=["public_health", "federalism", "report:customary"],
            influence_targets=["law:ca:public_health_act", "policy:ca:intergovernmental-health"],
        ),
    ]
    return {report.report_id: report for report in reports}


def export_inquiry_reports() -> dict[str, dict[str, Any]]:
    graph = build_sample_inquiries()
    return {report_id: asdict(report) for report_id, report in graph.items()}
