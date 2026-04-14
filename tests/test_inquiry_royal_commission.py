from __future__ import annotations

from src.ontology.inquiry_royal_commission import (
    inquiry_contract,
    build_sample_inquiries,
    export_inquiry_reports,
)


def test_inquiry_contract_distinguishes_advisory_role():
    contract = inquiry_contract()
    assert "advisory" in contract["scope"]
    constraints = list(contract["constraints"])
    assert any("never binding authority" in constraint for constraint in constraints)
    assert contract["authority_signal"].startswith("derived-only")
    assert "royal commission" in contract["justification"]


def test_sample_inquiries_include_influence_targets():
    inquiries = build_sample_inquiries()
    assert "inquiry:aus:rcs:2009:banking" in inquiries
    assert "law:aus:consumer_credit" in inquiries["inquiry:aus:rcs:2009:banking"].influence_targets
    assert "executive_power" in inquiries["inquiry:aus:rcs:2009:banking"].advisory_tags
    assert inquiries["inquiry:uk:rcs:2015:child_protection"].jurisdiction == "United Kingdom"


def test_exported_reports_preserve_dates():
    exported = export_inquiry_reports()
    canada = exported["inquiry:ca:commission:2020:healthcare"]
    assert canada["issued_date"] == "2020-08-30"
    assert "federalism" in canada["summary"].lower() or "federal" in canada["summary"].lower()
