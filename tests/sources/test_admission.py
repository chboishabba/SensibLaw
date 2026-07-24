from src.sources.admission import (
    OFFLINE_HCA_REGRESSION_PROFILE,
    admission_manifest,
    classify_catalogue,
)


def test_hca_profile_keeps_transport_as_evidence_but_out_of_parser() -> None:
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
            {
                "source_revision_ref": "source:duplicate",
                "source_role": "duplicate_caption",
            },
            {"source_revision_ref": "source:unknown", "source_role": "unknown"},
        ),
        profile=OFFLINE_HCA_REGRESSION_PROFILE,
    )
    assert [row.source_revision_ref for row in receipts if row.compile_eligible] == [
        "source:transcript"
    ]
    assert {
        row.source_revision_ref for row in receipts if row.admission_state == "evidence_only"
    } == {"source:search", "source:oembed", "source:recording"}
    assert {
        row.source_revision_ref for row in receipts if row.admission_state == "exclude"
    } == {"source:duplicate", "source:unknown"}

    manifest = admission_manifest(receipts)
    assert manifest["counts"] == {"compile": 1, "evidence_only": 3, "exclude": 2}
    assert manifest["parser_admitted_revision_refs"] == ["source:transcript"]
    assert manifest["network_activity_permitted"] is False
