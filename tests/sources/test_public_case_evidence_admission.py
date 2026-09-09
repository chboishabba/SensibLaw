from src.sources.admission import PUBLIC_CASE_EVIDENCE_PROFILE, admit_source


def test_public_case_reporting_can_compile_without_truth_promotion() -> None:
    receipt = admit_source(
        {
            "source_revision_ref": "source:case:report",
            "source_role": "news_report",
            "semantic_scope": "reported_case_evidence",
        },
        profile=PUBLIC_CASE_EVIDENCE_PROFILE,
    )
    row = receipt.to_dict()
    assert receipt.compile_eligible is True
    assert row["authority"] == "catalogue_admission_only"
    assert row["semantic_state_promoted"] is False
    assert row["legal_truth_closed"] is False


def test_public_case_profile_does_not_compile_anonymous_republication() -> None:
    receipt = admit_source(
        {
            "source_revision_ref": "source:case:anonymous-republication",
            "source_role": "anonymous_republication",
        },
        profile=PUBLIC_CASE_EVIDENCE_PROFILE,
    )
    assert receipt.compile_eligible is False
    assert receipt.exclusion_reason == "unattributed_republication_not_compile_eligible"


def test_public_case_social_pointer_is_discovery_only() -> None:
    receipt = admit_source(
        {
            "source_revision_ref": "source:case:social-pointer",
            "source_role": "social_post_pointer",
        },
        profile=PUBLIC_CASE_EVIDENCE_PROFILE,
    )
    assert receipt.evidence_only is True
    assert receipt.compile_eligible is False
