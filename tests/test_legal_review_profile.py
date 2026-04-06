import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.ingestion.media_adapter import TextDocumentMediaAdapter, parse_canonical_text
from src.policy.legal_review_profile import build_legal_review_extract


def test_build_legal_review_extract_emits_review_text_from_parsed_units():
    adapter = TextDocumentMediaAdapter(source_artifact_ref="legal-review")
    canonical = adapter.adapt("4 The board must consider section 15 before acting.")
    parsed_envelope = parse_canonical_text(canonical, parse_profile="legal_review")

    extract = build_legal_review_extract(
        parsed_envelope,
        lane="gwb",
        family_id="gwb_legal_review",
        cohort_id="gwb_legal_review_v1",
        root_artifact_id="gwb_legal_review_v1",
        source_family="gwb_legal_review",
        source_kind="review_source_text",
    )

    assert extract["schema_version"] == "sl.legal_review_extract.v0_1"
    assert extract["parse_profile"] == "legal_review"
    assert extract["text_id"] == canonical.text_id
    assert extract["envelope_id"] == parsed_envelope.envelope_id
    assert extract["parser_receipt"] == {
        "parser_version": "canonical_text_parser_v1",
        "parse_profile": "legal_review",
        "segment_count": 1,
        "unit_count": 1,
    }
    assert len(extract["review_claim_records"]) == 1

    record = extract["review_claim_records"][0]
    assert record["state"] == "review_claim"
    assert record["state_basis"] == "parsed_envelope_unit"
    assert record["evidence_status"] == "review_only"
    assert record["review_text"] == {
        "text": "4 The board must consider section 15 before acting.",
        "text_role": "parsed_unit_text",
        "source_kind": "review_source_text",
        "anchor_refs": {
            "text_id": canonical.text_id,
            "segment_id": canonical.segments[0].segment_id,
            "unit_id": f"{canonical.segments[0].segment_id}:unit:0",
            "start_char": 0,
            "end_char": len(canonical.text),
            "order_index": 0,
            "media_type": "text",
            "parse_profile": "legal_review",
        },
        "text_ref": {
            "text_id": canonical.text_id,
            "segment_id": canonical.segments[0].segment_id,
            "unit_id": f"{canonical.segments[0].segment_id}:unit:0",
            "envelope_id": parsed_envelope.envelope_id,
        },
    }
    assert "review_candidate" not in record
    assert "review_alignment" not in extract


def test_build_legal_review_extract_emits_weak_singleton_candidate_only_when_hint_present():
    adapter = TextDocumentMediaAdapter(source_artifact_ref="legal-review-singleton")
    canonical = adapter.adapt("5 The authority shall maintain records.")
    parsed_envelope = parse_canonical_text(canonical, parse_profile="legal_review")

    extract = build_legal_review_extract(
        parsed_envelope,
        lane="gwb",
        family_id="gwb_legal_review",
        cohort_id="gwb_legal_review_v1",
        root_artifact_id="gwb_legal_review_v1",
        source_family="gwb_legal_review",
        singleton_target_hint={
            "candidate_id": "target:1",
            "candidate_kind": "review_item_target",
        },
    )

    candidate = extract["review_claim_records"][0]["review_candidate"]
    assert candidate["candidate_id"] == "target:1"
    assert candidate["candidate_kind"] == "review_item_target"
    assert candidate["selection_basis"] == {
        "selection_mode": "explicit_singleton_hint",
        "parse_profile": "legal_review",
    }
    assert "target_proposition_id" not in candidate
