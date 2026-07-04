from SensibLaw.src.sources.national_archives.brexit_national_archives_lane import (
    build_operator_contract,
)


def test_follow_contract_articulates_constraints() -> None:
    contract = build_operator_contract()
    assert contract["scope"].startswith("bounded UK National Archives")
    assert any("crossrefs" in constraint for constraint in contract["constraints"])
    assert "authority" in contract["authority_signal"]
    assert any("translation" in constraint for constraint in contract["constraints"])
