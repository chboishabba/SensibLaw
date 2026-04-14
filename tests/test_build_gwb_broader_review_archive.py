from pathlib import Path
import json

from SensibLaw.scripts.build_gwb_broader_review import build_gwb_broader_review


def test_build_outputs_archive_rows(tmp_path: Path, monkeypatch):
    def fake_fetch(limit: int = 1, **_kwargs):
        return [
            {
                "doc_id": "NA.TEST",
                "title": "Test",
                "collection": "UK National Archives",
                "url": "https://example.com",
                "authority_role": "test",
                "intent_tags": ("test",),
                "anchor_date": "2024-01-01",
                "text_excerpt": "Live excerpt",
                "document_text": "Live document text",
                "provenance": {"lane": "NA.TEST"},
                "live_fetch": True,
            }
        ]

    monkeypatch.setattr(
        "SensibLaw.scripts.build_gwb_broader_review.fetch_brexit_archive_records",
        fake_fetch,
    )
    result = build_gwb_broader_review(output_dir=tmp_path)
    payload = json.loads(Path(result["artifact_path"]).read_text())
    assert payload.get("archive_follow_rows")
    assert payload["archive_follow_rows"][0]["doc_id"] == "NA.TEST"
    assert payload["summary"]["archive_follow_count"] == 1
    assert payload["summary"]["archive_follow_live_count"] == 1
    workflow = payload["workflow_summary"]
    assert workflow["stage"] == "archive"
    assert "archive follow" in workflow["reason"].lower()
    assert any(
        row.get("source_family") == "national_archives"
        for row in payload["source_review_rows"]
    )
