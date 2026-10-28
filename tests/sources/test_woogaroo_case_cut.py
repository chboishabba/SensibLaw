"""Woogaroo P0 candidate case contracts, native SensibLaw admission.
These tests do not claim any actual case evidence or Court result.
"""
import pytest

from src.sources.woogaroo_case_cut import (
    GROUNDS, MATTER_REF, SCENIC, SPRINGVIEW, case_cut_packet,
    eligible_as_springview_merits_evidence, source_admission_snapshot,
)


def test_case_has_seven_unpaid_grounds_and_one_referral():
    packet = case_cut_packet()
    assert packet["matter_ref"] == MATTER_REF
    assert packet["action_ref"] == SPRINGVIEW
    assert packet["case_stage"] == "source_written_candidate_unfiled"
    assert len(GROUNDS) == len(packet["grounds"]) == 7
    assert len({g["ground_ref"] for g in packet["grounds"]}) == 7
    assert all(g["gate"] == 0 for g in packet["grounds"])
    assert all(
        g["case_error_proved"] is False
        and g["positive_witness_refs"] == []
        and g["negative_witness_refs"] == []
        for g in packet["grounds"]
    )
    assert not packet["signed_federal_approval_paid"]
    assert not packet["secretary_95c_paid"]
    assert not packet["applicant_standing_paid"]
    assert not packet["actual_filing_paid"]
    assert not packet["creates_legal_authority"]


def test_catalogue_admission_is_not_paid_source_revision_or_legal_truth():
    rows = source_admission_snapshot()
    assert len(rows) == 7
    assert len({r["key"] for r in rows}) == 7
    assert all(r["original_url"].startswith("https://") for r in rows)
    assert all(r["admission"]["source_revision_ref"].startswith("locator-only:") for r in rows)
    assert all(
        not r["persisted_revision_paid"]
        and not r["source_bytes_materialised"]
        and r["canonical_content_sha256"] is None
        and r["exact_span_ref"] is None
        and not r["parser_execution_authorised"]
        and not r["exact_span_paid"]
        and not r["case_fact_paid"]
        and not r["minister_delivery_paid"]
        for r in rows
    )
    assert all(not r["admission"]["semantic_state_promoted"] for r in rows)
    assert all(not r["admission"]["legal_truth_closed"] for r in rows)
    law = next(r for r in rows if r["key"] == "epbc-operative-law")
    assert law["admission"]["admission_state"] == "compile"
    assert law["exact_span_paid"] is False


def test_scenic_activity_can_be_standing_input_but_not_springview_merits():
    rows = source_admission_snapshot()
    scenic = next(row for row in rows if row["key"] == "swfg-scenic-letter")
    assert scenic["epbc_action"] == SCENIC
    assert scenic["standing_activity_candidate"] is True
    assert not eligible_as_springview_merits_evidence("swfg-scenic-letter")
    assert eligible_as_springview_merits_evidence("qut-springview-letter-2026")
    assert eligible_as_springview_merits_evidence("stockland-springview-faq")
    with pytest.raises(KeyError):
        eligible_as_springview_merits_evidence("unseen-source")


def test_submission_and_publisher_claims_remain_evidence_only():
    rows = source_admission_snapshot()
    for name in ("qut-springview-letter-2026", "stockland-springview-faq",
                 "swfg-scenic-letter", "epbc-approval-status",
                 "koala-conservation-advice-2022", "koala-recovery-plan-2022"):
        source = next(r for r in rows if r["key"] == name)
        assert source["admission"]["admission_state"] == "evidence_only"
    assert all(r["admission"]["authority"] == "catalogue_admission_only" for r in rows)


def test_packet_deterministic_and_discriminators_nonblank():
    assert case_cut_packet() == case_cut_packet()
    assert all(
        g["requested_discriminator"] and g["statutory_hook"]
        for g in case_cut_packet()["grounds"]
    )
