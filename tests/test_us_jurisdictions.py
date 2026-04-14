from __future__ import annotations

from src.sources.us_jurisdictions import canonical_us_jurisdictions


def test_us_jurisdictions_cover_states_and_territories() -> None:
    jurisdictions = canonical_us_jurisdictions()
    expected_codes = {
        "US.FED",
        "US.CA",
        "US.NY",
        "US.TX",
        "US.FL",
        "US.PR",
        "US.GU",
        "US.VI",
        "US.AS",
    }
    actual_codes = {jurisdiction["code"] for jurisdiction in jurisdictions}
    assert expected_codes <= actual_codes
    assert all(jurisdiction["sovereign"] == "US" for jurisdiction in jurisdictions)
