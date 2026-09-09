from __future__ import annotations

from src.ontology.wikidata_nat_source_discovery import (
    build_same_source_identity_receipt,
    normalize_discovery_provider_receipt,
)
from src.ontology.wikidata_nat_source_lineage import build_source_lineage_receipt


def test_official_report_can_be_source_of_source_without_same_source_admission() -> None:
    demand = {
        "demand_ref": "nat-source-discovery-demand:diva-10191",
        "original_locator": "http://urn.kb.se/resolve?urn=urn:nbn:se:naturvardsverket:diva-10191",
    }
    discovery = normalize_discovery_provider_receipt(
        demand,
        {
            "provider": "web_search",
            "provider_call_ref": "discovery-2026-09-09",
            "candidates": [
                {
                    "url": "https://naturvardsverket.diva-portal.org/smash/get/diva2%3A1665109/FULLTEXT01.pdf",
                    "title": "Miljöledning i staten 2021 : En redovisning",
                    "rank": 1,
                }
            ],
        },
    )
    candidate = discovery["candidates"][0]
    identity = build_same_source_identity_receipt(
        demand,
        candidate,
        disposition="different_source",
        verifier_reference="official-diva-record-review",
        identity_evidence_locator=(
            "DiVA record diva2:1665109 has permanent URN diva-10265; "
            "report footnote 5 separately names diva-10191"
        ),
    )
    lineage = build_source_lineage_receipt(
        identity,
        relation="source_of_source",
        lineage_evidence_locator=(
            "Miljöledning i staten 2021, footnote 5 -> "
            "urn:nbn:se:naturvardsverket:diva-10191"
        ),
        derived_query_hints=[
            '"urn:nbn:se:naturvardsverket:diva-10191"',
            '"Miljöledning i staten 2021 redovisade uppgifter"',
        ],
    )

    assert identity["same_source_identity_trit"] == -1
    assert identity["same_source_identity_paid"] is False
    assert lineage["relation"] == "source_of_source"
    assert lineage["alternate_fetch_admitted"] is False
    assert lineage["source_support_paid"] is False
    assert '"urn:nbn:se:naturvardsverket:diva-10191"' in lineage["derived_query_hints"]
