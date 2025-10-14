from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))


from src.reliability.pre_brief import (  # noqa: E402
    DocumentSection,
    Exhibit,
    FactClaim,
    build_pre_brief,
)


def _sample_sections() -> list[DocumentSection]:
    return [
        DocumentSection(
            anchor="para-1",
            heading="Parties",
            text="Applicant: Alice Smith\nRespondent: Bob Jones",
        ),
        DocumentSection(
            anchor="para-2",
            heading="Key dates",
            text="Filing date: 1 March 2023\nHearing on 2023-06-15",
        ),
        DocumentSection(
            anchor="para-3",
            heading="Orders sought",
            text="Orders sought:\n(a) That the child live with the Applicant.\n(b) That time with the Respondent be supervised.",
        ),
        DocumentSection(
            anchor="para-4",
            heading="Primary considerations",
            text=(
                "The benefit to the child of a meaningful relationship with both parents is acknowledged. "
                "The need to protect the child from physical harm is paramount."
            ),
        ),
        DocumentSection(
            anchor="para-5",
            heading="Chronology",
            text=(
                "On 5 April 2023, the incident occurred at the family home. "
                "On 7 April 2023, the incident occurred at the family home. "
                "The parenting questionnaire must be filed by 30 April 2023."
            ),
        ),
    ]


def _sample_facts_and_exhibits() -> tuple[list[FactClaim], list[Exhibit]]:
    facts = [
        FactClaim(
            id="fact-1",
            text="Mother alleges incident occurred in April",
            anchor="para-5",
            exhibit_ids=["ex-1"],
        ),
        FactClaim(
            id="fact-2",
            text="Father failed to attend mediation",
            anchor="para-6",
            exhibit_ids=[],
        ),
    ]
    exhibits = [
        Exhibit(
            id="ex-1",
            description="Photographs of damage",
            anchor="exhibit-1",
            fact_ids=["fact-1"],
        ),
        Exhibit(
            id="ex-2",
            description="Mediation attendance sheet",
            anchor="exhibit-2",
            fact_ids=[],
        ),
    ]
    return facts, exhibits


class TestPreBrief:
    def test_extractions_and_flags(self) -> None:
        sections = _sample_sections()
        facts, exhibits = _sample_facts_and_exhibits()
        pre_brief = build_pre_brief(sections, facts=facts, exhibits=exhibits)

        parties = {entry.role: entry for entry in pre_brief.parties}
        assert parties["Applicant"].name == "Alice Smith"
        assert parties["Applicant"].anchor == "para-1"
        assert parties["Respondent"].name == "Bob Jones"

        assert any(
            date.label.lower().startswith("filing") for date in pre_brief.key_dates
        )
        assert all(entry.anchor for entry in pre_brief.key_dates)

        order_texts = {order.text for order in pre_brief.orders_sought}
        assert "That the child live with the Applicant." in order_texts
        assert "That time with the Respondent be supervised." in order_texts

        factor_hits = pre_brief.s60cc_hits
        assert "benefit_meaningful_relationship" in factor_hits
        assert any(
            hit.anchor == "para-4"
            for hit in factor_hits["benefit_meaningful_relationship"]
        )
        assert "need_to_protect_from_harm" in factor_hits

        assert pre_brief.contradictions, (
            "expected contradiction from differing timestamps"
        )
        contradiction = pre_brief.contradictions[0]
        assert "incident occurred" in contradiction.event
        assert len(contradiction.dates) == 2
        assert "para-5" in contradiction.anchors

        deadline_flags = [
            flag for flag in pre_brief.red_flags if flag.kind == "deadline"
        ]
        assert deadline_flags, "deadline should be flagged"
        assert all(flag.anchor == "para-5" for flag in deadline_flags)

        inconsistency_flags = [
            flag for flag in pre_brief.red_flags if flag.kind == "inconsistency"
        ]
        assert inconsistency_flags, "contradiction should create an inconsistency flag"

        proof_debt = pre_brief.proof_debt
        fact_ids = {item.identifier for item in proof_debt.facts_without_exhibits}
        assert "fact-2" in fact_ids
        exhibit_ids = {
            item.identifier for item in proof_debt.exhibits_without_relevance
        }
        assert "ex-2" in exhibit_ids

    def test_deterministic_output(self) -> None:
        sections = _sample_sections()
        facts, exhibits = _sample_facts_and_exhibits()

        first = build_pre_brief(sections, facts=facts, exhibits=exhibits).to_dict()
        second = build_pre_brief(sections, facts=facts, exhibits=exhibits).to_dict()

        assert first == second

        digest = hashlib.sha256(
            json.dumps(first, sort_keys=True).encode("utf-8")
        ).hexdigest()
        digest_again = hashlib.sha256(
            json.dumps(second, sort_keys=True).encode("utf-8")
        ).hexdigest()
        assert digest == digest_again
