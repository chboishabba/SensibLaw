from __future__ import annotations

import pytest

from src.sources.us_official import (
    OfficialDocMetadata,
    build_congress_gov_doc,
    build_govinfo_doc,
    build_grouped_official_packet,
    build_follow_contract,
)


def test_grouped_packet_contains_both_lanes() -> None:
    packet = build_grouped_official_packet(
        [build_congress_gov_doc(), build_govinfo_doc()], packet_id="moonshot-us-official-1"
    )

    assert packet["doc_count"] == 2
    assert set(packet["lane_ids"]) == {
        "gwb_govinfo_browse",
        "wikidata_nat_wdu_congress",
    }
    assert packet["constraints"]["deterministic_ids"] is True
    assert "Congress.gov" in packet["constraints"]["official_sources"]
    assert "GovInfo" in packet["constraints"]["official_sources"]
    assert packet["combined_policy_flags"] == ["budget", "debt_limit", "infrastructure"]


def test_grouped_packet_requires_unique_docs() -> None:
    doc = build_congress_gov_doc()
    with pytest.raises(ValueError, match="Duplicate official doc id"):
        build_grouped_official_packet([doc, doc], packet_id="dup")


def test_grouped_packet_requires_metadata() -> None:
    bad_doc = OfficialDocMetadata(
        lane_id="fake",
        source_name="Fake",
        doc_id="",
        title="",
        published_date="",
        doc_type="",
        policy_flags=(),
        uri="",
    )
    with pytest.raises(ValueError, match="doc_id"):
        build_grouped_official_packet([bad_doc], packet_id="bad")


def test_follow_contract_builds_requests() -> None:
    contract = build_follow_contract([build_congress_gov_doc(), build_govinfo_doc()])
    assert contract["strategy"] == "bounded_official_follow"
    assert len(contract["requests"]) == 2
    first = contract["requests"][0]
    assert first["doc_id"].startswith("congress") or first["doc_id"].startswith("govinfo")
    assert first["policy_flags"]
    assert contract["adapter_constraints"]["tie_policy_flags"] is True
