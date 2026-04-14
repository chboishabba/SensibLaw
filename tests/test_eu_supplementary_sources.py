from __future__ import annotations

from src.sources.eu_supplementary_sources import canonical_eu_supplementary_sources


def test_eu_supplementary_sources_defined() -> None:
    sources = canonical_eu_supplementary_sources()
    names = {source["name"] for source in sources}
    expected = {
        "Court of Justice of the European Union (Curia)",
        "European Central Bank Legal Acts",
        "European Commission Legal Documents",
    }
    assert expected <= names
    assert all(source["jurisdiction"] == "EU" for source in sources)
    kinds = {source["source_kind"] for source in sources}
    assert "case_law" in kinds
    assert "monetary_regulation" in kinds
    assert "commission_legal_docs" in kinds
