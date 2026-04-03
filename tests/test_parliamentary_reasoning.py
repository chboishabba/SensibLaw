from SensibLaw.src.proof.parliamentary_reasoning import (
    ParliamentaryReasoningChain,
    build_parliamentary_proof_artifact,
    build_parliamentary_reasoning_fixture,
    build_primary_proving_cases,
)


def test_parliamentary_reasoning_fixture_emphasizes_nonlaw():
    chain = ParliamentaryReasoningChain(
        debate_id="IRAQ-PAR-2026-07",
        parliamentary_body="Iraqi Council of Representatives",
        interpretation_quote="Debate highlighted how the UN Security Council language can be read as advisory before domestic codification.",
        argument_linked_law="UNSCR 678",
        resulting_signal="interpretive-argument",
    )
    fixture = build_parliamentary_reasoning_fixture(chain)

    assert fixture["interpretation"]["quote"].startswith("Debate highlighted")
    assert fixture["result"]["nature"] == "interpretive argument"
    assert fixture["separation"]["interpretation_not_binding"] is True
    assert fixture["separation"]["law_unchANGED"] == "UNSCR 678"
    cases = build_primary_proving_cases()
    iraq = next(item for item in cases if item["case"] == "iraq")
    brexit = next(item for item in cases if item["case"] == "brexit")
    assert iraq["fixture"]["result"]["signal"] == "interpretive-argument"
    assert brexit["fixture"]["result"]["signal"] == "resolved-interpretation"
    assert "source_unit" in iraq
    assert "source_unit" in brexit
    assert iraq["source_unit"]["source_unit_id"].startswith("sourceunit:parliamentary")
    assert brexit["source_unit"]["claim_type"] == "statutory_oversight"
    assert "normalized_source_unit" in brexit["source_unit"]
    assert "Iraqi Council" in iraq["fixture"]["interpretation"]["quote"]
    artifact = build_parliamentary_proof_artifact()
    assert artifact["broader_review_adjacent"] is True
    assert any(c["broader_context"]["context"].startswith("Iraqi Council") for c in artifact["cases"])
    assert artifact["quality_notes"]["iraq"].startswith("Non-justiciable")
    cases = build_primary_proving_cases()
    iraq_case = next(item for item in cases if item["case"] == "iraq")
    assert iraq_case["fixture"]["interpretation"]["source_reference"] == "Iraqi Council Committee report"
