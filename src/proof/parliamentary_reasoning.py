from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from src.sources.parliamentary_transcript_source_unit import (
    ClauseIR,
    build_parliamentary_source_unit_from_transcript,
)


@dataclass(frozen=True)
class ParliamentaryReasoningChain:
    debate_id: str
    parliamentary_body: str
    interpretation_quote: str
    argument_linked_law: str
    resulting_signal: str
    source_reference: str | None = None


def build_parliamentary_reasoning_fixture(
    chain: ParliamentaryReasoningChain,
) -> Mapping[str, object]:
    return {
        "debate": {
            "id": chain.debate_id,
            "body": chain.parliamentary_body,
        },
        "interpretation": {
            "quote": chain.interpretation_quote,
            "argument": chain.argument_linked_law,
            "source_reference": chain.source_reference or chain.parliamentary_body,
        },
        "result": {
            "signal": chain.resulting_signal,
            "nature": "interpretive argument",
        },
        "separation": {
            "interpretation_not_binding": True,
            "law_unchANGED": chain.argument_linked_law,
        },
    }


def _build_iraq_source_unit() -> dict[str, object]:
    clause = ClauseIR(
        clause_label="UNSCR 678 advisory note",
        clause_reference="iraq-clause-678",
        interpretive_note="Iraqi Council transcripts tie the UNSC authorization debate to ministerial statements without creating binding law.",
        legal_claim_type="defense_authority",
        language="en",
    )
    return build_parliamentary_source_unit_from_transcript(
        transcript_id="iraq-council-2026-07",
        utterance_index=2,
        session_label="Iraqi Council of Representatives debate on UNSC authorization",
        session_url="https://irc.gov.iq/debates/2026-07-01",
        speaker_name="Council Member Al-Amin",
        speaker_role="Defense Committee Lead",
        statement_text="Our parliamentary record affirms UNSC Resolution 678 remains advisory unless codified through domestic law.",
        claim_type="defense_authority",
        jurisdiction="IQ",
        source_family="iraqi_parliament",
        clause_ir=clause,
        timestamp="2026-07-01T14:18:00Z",
    )


def _build_brexit_source_unit() -> dict[str, object]:
    clause = ClauseIR(
        clause_label="Withdrawal Act oversight",
        clause_reference="brexit-clause-wa2018",
        interpretive_note="Hansard debate paired the Withdrawal Agreement with domestic statute to cement parliamentary oversight.",
        legal_claim_type="statutory_oversight",
        language="en",
    )
    return build_parliamentary_source_unit_from_transcript(
        transcript_id="uk-hoc-brexit-2021",
        utterance_index=11,
        session_label="House of Commons Brexit debate",
        session_url="https://hansard.parliament.uk/commons/2021-03-29",
        speaker_name="MP Jane Smith",
        speaker_role="Shadow Trade Secretary",
        statement_text="If the Withdrawal Agreement is now domesticated through the EU Withdrawal Act, parliamentary oversight must remain intact.",
        claim_type="statutory_oversight",
        jurisdiction="UK",
        source_family="uk_parliament",
        clause_ir=clause,
        timestamp="2021-03-29T10:12:00Z",
    )


def build_primary_proving_cases() -> list[Mapping[str, object]]:
    iraq_chain = ParliamentaryReasoningChain(
        debate_id="IRAQ-PAR-2026-07",
        parliamentary_body="Iraqi Council of Representatives",
        interpretation_quote=(
            "Iraqi Council transcripts reiterated that UNSC Resolution 678 remains advisory until our legal order codifies it."
        ),
        argument_linked_law="UNSCR 678",
        resulting_signal="interpretive-argument",
        source_reference="Iraqi Council Committee report",
    )
    brexit_chain = ParliamentaryReasoningChain(
        debate_id="UK-HOC-BREXIT-2021",
        parliamentary_body="UK House of Commons",
        interpretation_quote="Debate concluded the Withdrawal Agreement now operates via domestic statute.",
        argument_linked_law="EU Withdrawal Act 2018",
        resulting_signal="resolved-interpretation",
    )
    return [
        {
            "case": "iraq",
            "fixture": build_parliamentary_reasoning_fixture(iraq_chain),
            "source_unit": _build_iraq_source_unit(),
            "broader_context": {
                "review_family": "broader_review_parliamentary",
                "context": "Iraqi Council / UNSC advisory review",
            },
        },
        {
            "case": "brexit",
            "fixture": build_parliamentary_reasoning_fixture(brexit_chain),
            "source_unit": _build_brexit_source_unit(),
            "broader_context": {
                "review_family": "broader_review_parliamentary",
                "context": "Hansard + Withdrawal Act nexus",
            },
        },
    ]


def build_parliamentary_proof_artifact() -> Mapping[str, object]:
    cases = build_primary_proving_cases()
    return {
        "artifact_family": "parliamentary_reasoning",
        "summary": "Primary proving cases for Iraq (advisory debate) and Brexit (resolved statute).",
        "broader_review_adjacent": True,
        "quality_notes": {
            "iraq": "Non-justiciable framing preserved via Iraqi Council advisory note.",
            "brexit": "Resolved via domestic statute + Withdrawal agreement confirmation.",
        },
        "cases": cases,
        "separation": {
            "debate_vs_law": "interpretation not binding yet tied to review context",
        },
    }
