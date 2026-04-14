from SensibLaw.src.sources.standards_reference import canonical_standards_references


def test_assertiveness_flags_present() -> None:
    refs = canonical_standards_references()
    assert any(ref.assertiveness.startswith("non") for ref in refs)


def test_metadata_contains_applicability() -> None:
    metadata = canonical_standards_references()[1].build_metadata("risk appetite")
    assert "applicability" in metadata
    assert "risk" in metadata["applicability"]
