from SensibLaw.src.sources.worldbank.worldbank_follow_contract import (
    normalize_worldbank_follow_input,
    worldbank_follow_contract,
)


def test_worldbank_contract_constraints() -> None:
    contract = worldbank_follow_contract()
    assert contract["scope"].startswith("bounded World Bank")
    assert any("crossrefs" in constraint for constraint in contract["constraints"])
    assert any("lineage" in constraint for constraint in contract["constraints"])
    assert "authority" in contract["authority_signal"]
    normalized = normalize_worldbank_follow_input({
        "document_id": "WB-123",
        "title": "Assessment",
        "summary_snippet": "Key findings",
        "crossrefs": ["sect1"],
        "lineage_refs": ["policy-doc"],
        "translation_notes": ["translated into French"],
    })
    assert normalized.lineage_refs
    assert normalized.translation_notes
