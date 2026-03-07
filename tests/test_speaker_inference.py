from __future__ import annotations

from src.reporting.structure_report import TextUnit
from src.text.speaker_inference import infer_speakers


def test_speaker_inference_uses_explicit_message_headers():
    units = [TextUnit("u1", "src1", "transcript_file", "[5/3/26 8:50 pm] Dave: Thanks for the feedback.")]
    receipts = infer_speakers(units)
    assert receipts[0].inferred_speaker == "speaker:dave"
    assert receipts[0].confidence == "high"
    assert receipts[0].abstained is False


def test_speaker_inference_abstains_on_timing_only_ranges():
    units = [TextUnit("u1", "src1", "transcript_file", "[00:00:00,030 -> 00:00:21,970] Thanks.")]
    receipts = infer_speakers(units)
    assert receipts[0].abstained is True
    assert receipts[0].abstain_reason == "timing_only"


def test_speaker_inference_maps_qa_to_known_participants():
    units = [
        TextUnit("u1", "hearing-1", "transcript_file", "Q: Where were you?"),
        TextUnit("u2", "hearing-1", "transcript_file", "A: At home."),
    ]
    receipts = infer_speakers(units, known_participants_by_source={"hearing-1": ["counsel", "witness"]})
    assert receipts[0].inferred_speaker == "speaker:counsel"
    assert receipts[1].inferred_speaker == "speaker:witness"
    assert receipts[0].confidence == "low"


def test_speaker_inference_coalesces_single_gap_between_same_speakers():
    units = [
        TextUnit("u1", "src1", "transcript_file", "[5/3/26 8:50 pm] Dave: one"),
        TextUnit("u2", "src1", "transcript_file", "continued thought without explicit speaker"),
        TextUnit("u3", "src1", "transcript_file", "[5/3/26 8:52 pm] Dave: two"),
    ]
    receipts = infer_speakers(units)
    assert receipts[1].inferred_speaker == "speaker:dave"
    assert receipts[1].confidence == "low"
    assert "neighbor_consensus" in receipts[1].reasons


def test_speaker_inference_supports_messenger_style_bracketed_rows():
    units = [TextUnit("u1", "src1", "messenger_test_db", "[2024-11-13 02:08:53] Chboi Shabba: hello there")]
    receipts = infer_speakers(units)
    assert receipts[0].inferred_speaker == "speaker:chboi_shabba"
    assert receipts[0].confidence == "high"
    assert receipts[0].abstained is False
