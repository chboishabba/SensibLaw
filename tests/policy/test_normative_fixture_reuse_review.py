import json
from pathlib import Path

from src.policy.normative_fixture_reuse_review import review_normative_excerpt_packs

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "normative"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_iso_excerpt_packs_are_bounded_and_reuse_normative_policy_profile():
    report = review_normative_excerpt_packs(
        [
            ("iso_42001_excerpt_pack_v1.json", _load("iso_42001_excerpt_pack_v1.json")),
            ("iso_42001_excerpt_pack_v2.json", _load("iso_42001_excerpt_pack_v2.json")),
        ]
    )

    assert report["schema_version"] == "sl.normative_fixture_reuse_review.v0_1"
    assert report["review_scope"] == "bounded_excerpt_pack_fixture_quality_and_profile_reuse"
    assert report["broad_catalog_ingestion_used"] is False
    assert report["parse_profile"] == "normative_policy"
    assert report["pack_count"] == 2
    assert report["all_packs_bounded"] is True
    assert report["all_packs_reuse_profile"] is True
    assert report["all_packs_provenance_complete"] is True
    assert report["document_refs"] == ["iso_42001"]
    assert report["clause_refs"] == ["4", "5"]
    assert [row["fixture_name"] for row in report["packs"]] == [
        "iso_42001_excerpt_pack_v1.json",
        "iso_42001_excerpt_pack_v2.json",
    ]
    assert [row["statement_count"] for row in report["packs"]] == [1, 1]
    assert all(row["quality_status"] == "fixture_quality_pass" for row in report["packs"])


def test_fixture_review_fails_closed_on_unbounded_or_incomplete_pack():
    report = review_normative_excerpt_packs(
        [
            (
                "bad.json",
                {
                    "text": "x" * 4097,
                    "provenance": {
                        "document_ref": "iso_42001",
                        "source_class": "text_source",
                        "source_subtype": "excerpt_pack",
                        "clause_refs": [],
                    },
                },
            )
        ]
    )

    row = report["packs"][0]
    assert report["all_packs_bounded"] is False
    assert report["all_packs_provenance_complete"] is False
    assert report["all_packs_reuse_profile"] is False
    assert row["quality_status"] == "fixture_quality_hold"
    assert row["issues"] == [
        "excerpt_too_large",
        "clause_refs_missing",
    ]
