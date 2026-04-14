from src.sources.parliamentary_transcript_source_unit import (
    ClauseIR,
    build_parliamentary_source_unit_from_transcript,
)


def _base_payload(**overrides):
    default = dict(
        transcript_id="british-hansard-2026-03-15",
        utterance_index=3,
        session_label="House of Commons, Brexit debate",
        session_url="https://hansard.parliament.uk/commons/2026-03-15",
        speaker_name="MP Jane Smith",
        speaker_role="Shadow Trade Secretary",
        statement_text="We must ensure the clause preserves parliamentary oversight of Article 50 implementation.",
        claim_type="statutory_oversight",
        jurisdiction="UK",
        source_family="uk_parliament",
        clause_ir=ClauseIR(
            clause_label="Article 50 oversight",
            clause_reference="clause-50a",
            interpretive_note="Links oversight duties to constitutional conventions.",
            legal_claim_type="statute_reference",
        ),
    )
    default.update(overrides)
    return build_parliamentary_source_unit_from_transcript(**default)


def test_brexit_transcript_mapping_preserves_speaker_and_clause() -> None:
    payload = _base_payload()
    assert payload["speaker_identity"]["name"] == "MP Jane Smith"
    assert payload["claim_type"] == "statutory_oversight"
    assert payload["clause_ir"]["clause_label"].startswith("Article 50")
    normalized = payload["normalized_source_unit"]
    assert normalized["authority_level"] == "parliamentary_interpretive"
    assert "sourceunit:parliamentary" in payload["source_unit_id"]


def test_iraq_transcript_mapping_highlights_interpretive_note_and_language() -> None:
    clause = ClauseIR(
        clause_label="Iraq war authorization",
        clause_reference="resolution-1483",
        interpretive_note="Connects ministerial statements to authorization debates without creating binding law.",
        legal_claim_type="defense_authority",
        language="en",
    )
    payload = _base_payload(
        transcript_id="iraq-council-2025-11-10",
        utterance_index=7,
        session_label="Iraqi Council of Representatives debate",
        session_url="https://irc.gov.iq/debates/2025-11-10",
        speaker_name="Council President Abbas",
        speaker_role="Presiding Officer",
        statement_text="The authorization debate on Iraq 2002 remains a reference point for our coordination with the coalition.",
        claim_type="defense_authority",
        jurisdiction="IQ",
        source_family="iraqi_parliament",
        clause_ir=clause,
        timestamp="2025-11-10T15:23:00Z",
    )
    assert clause.interpretive_note in payload["clause_ir"]["interpretive_note"]
    normalized = payload["normalized_source_unit"]
    assert normalized["readiness_signals"]["claim_type"] == "defense_authority"
    assert payload["statement_snippet"].startswith("The authorization")
