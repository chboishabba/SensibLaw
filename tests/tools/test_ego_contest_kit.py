"""Tests for the ego-contest mitigation kit."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from src.tools.ego_contest import (
    EgoContestReport,
    build_batna_sheet,
    generate_cooling_off_macros,
    normalise_offers,
    run_ego_contest_kit,
    side_by_side_diff,
    tone_audit,
)


def test_tone_audit_flags_and_rewrites() -> None:
    communication = (
        "Dear Counsel,\n"
        "Your client refuses to provide payroll data and demands immediate payment.\n"
        "It also fails to acknowledge the inspection we offered.\n"
    )

    result = tone_audit(communication)

    triggers = [flag.trigger for flag in result.flags]
    assert triggers.count("refuses") == 1
    assert triggers.count("demands") == 1
    assert triggers.count("fails to") == 1

    suggestions = {flag.trigger: flag.suggestion for flag in result.flags}
    assert "has not agreed" in suggestions["refuses"]
    assert "requests" in suggestions["demands"]
    assert "has not yet" in suggestions["fails to"]

    diff = side_by_side_diff(communication, result.revised_text)
    # Ensure the diff replaces the contentious phrasing.
    rewritten_line = dict((line_no, after) for line_no, _, after in diff)
    assert "has not agreed to" in rewritten_line[2]
    assert "requests" in rewritten_line[2]
    assert "has not yet" in rewritten_line[3]


def test_offer_normaliser_structures_positions() -> None:
    offers = [
        "Payment: the client can settle between $80,000 and $95,000 provided instalments are quarterly.",
        "Disclosure pending: site logs within 14 days and subject to a safety review.",
    ]

    summaries = normalise_offers(offers)

    first = summaries[0].as_dict()
    assert first["issue"] == "Payment terms"
    assert "provided" in first["constraints"]
    assert first["acceptable_range"] == "$80,000 - $95,000"

    second = summaries[1].as_dict()
    assert second["issue"] == "Disclosure obligations"
    assert "within" in second["constraints"].lower()
    assert second["acceptable_range"] == "14"


def test_batna_sheet_and_macros() -> None:
    data = {
        "cost_to_hearing": "$45,000",
        "timeframe_to_hearing": "18 months",
        "disclosure_gaps": ["safety audit", "financial statements"],
    }

    batna = build_batna_sheet(data)
    assert batna.hearing_cost == "$45,000"
    assert "Outstanding disclosure" in batna.objective_risks[-1]

    macros = generate_cooling_off_macros(batna, tone_audit("refuses").flags)
    assert macros[0].startswith("Without prejudice")
    assert "refuses" in macros[-1]


def test_run_kit_returns_complete_report() -> None:
    communication = (
        "Team,\n"
        "The supplier refuses to schedule an inspection and demands new deposits.\n"
        "It fails to share the maintenance logs.\n"
    )
    offers = [
        "Settlement offer: between $50,000 and $60,000 with payment within 30 days.",
        "Disclosure: provide machine logs within 7 days pending confidentiality terms.",
    ]
    file_data = {
        "cost_to_hearing": "$60,000",
        "timeframe_to_hearing": "9 months",
        "disclosure_gaps": "maintenance logs, warranty certificates",
    }

    report = run_ego_contest_kit(communication, offers, file_data)
    assert isinstance(report, EgoContestReport)
    assert report.tone_audit.has_flags
    assert len(report.offers) == 2
    assert any("Without prejudice" in macro for macro in report.cooling_off_macros)
    assert any("maintenance logs" in risk for risk in report.batna_sheet.objective_risks)
    assert any("requests" in after for _, _, after in report.diff)

