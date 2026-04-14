from SensibLaw.src.sources.un.un_follow_contract import (
    normalize_un_follow_inputs,
    un_document_follow_contract,
)


def test_un_follow_contract_constraints() -> None:
    contract = un_document_follow_contract()
    assert contract["scope"].startswith("bounded UN document follow")
    assert any("crossrefs" in c for c in contract["constraints"])
    assert any("translation" in c for c in contract["constraints"])
    assert "authority" in contract["authority_signal"]
    input_shape = normalize_un_follow_inputs({
        "document_id": "UN123",
        "title": "Sample",
        "text_snippet": "Text",
        "crossrefs": ["sec1"],
        "resolution_sources": ["Res1"],
        "translation_links": ["https://example.com/translated"],
    })
    assert input_shape.document_id == "UN123"
    assert input_shape.translation_links
