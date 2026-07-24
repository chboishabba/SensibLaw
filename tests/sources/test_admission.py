from src.sources.admission import OFFLINE_HCA_REGRESSION_PROFILE, classify_catalogue


def test_hca_profile_excludes_transport_artifacts_before_parser_admission() -> None:
    receipts = classify_catalogue(
        (
            {
                "source_revision_ref": "source:transcript",
                "source_role": "hearing_transcript",
            },
            {"source_revision_ref": "source:search", "source_role": "search"},
            {"source_revision_ref": "source:oembed", "source_role": "oembed"},
            {
                "source_revision_ref": "source:recording",
                "source_role": "recording_page",
            },
        ),
        profile=OFFLINE_HCA_REGRESSION_PROFILE,
    )
    assert [row.source_revision_ref for row in receipts if row.compile_eligible] == [
        "source:transcript"
    ]
    assert {row.exclusion_reason for row in receipts if not row.compile_eligible} == {
        "search_not_substantive",
        "oembed_not_substantive",
        "recording_page_not_transcript_media",
    }
