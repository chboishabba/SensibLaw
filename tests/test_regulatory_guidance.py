from SensibLaw.src.follow.regulatory_guidance import (
    RegulatoryGuidanceUnit,
    build_regulatory_guidance_unit,
)


def test_regulatory_guidance_unit_preserves_separation():
    unit = RegulatoryGuidanceUnit(
        source_id="regulator:001",
        title="Banking Policy Guidance 2026",
        regulator="US Federal Reserve",
        policy_framework="Basel III compliance",
        compliance_influence="reference and soft compliance advice",
        binding_law_reference="Federal Reserve Act Section 13",
    )
    record = build_regulatory_guidance_unit(unit)

    assert record["source_family"] == "regulator_guidance"
    assert "binding_law_reference" in record
    assert record["separation"]["non_binding"] is True
    assert record["normative_influence"]["interpretive"] == "soft guidance"


def test_regulatory_guidance_without_binding_ref():
    unit = RegulatoryGuidanceUnit(
        source_id="regulator:002",
        title="EU Climate Advisory Note",
        regulator="European Commission",
        policy_framework="Green Deal preparatory actions",
        compliance_influence="signals advisory preference",
        interpretive_note="interpretive clarity only",
    )
    record = build_regulatory_guidance_unit(unit)

    assert record["normative_influence"]["interpretive"] == "interpretive clarity only"
    assert record["separation"]["binding_law"] is False
