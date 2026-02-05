from __future__ import annotations

from src.ingestion.span_signal_hypotheses import build_span_signal_hypotheses


def test_build_span_signal_hypotheses_detects_signals() -> None:
    text = (
        "1\n"
        "• Bullet point\n"
        "THIS HEADING\n"
        "Text with ??? and non-ascii café.\n"
        "Broken char: �"
    )
    hypotheses = build_span_signal_hypotheses(text)
    signal_types = {item.signal_type for item in hypotheses}

    assert "layout_artifact" in signal_types
    assert "list_marker" in signal_types
    assert "visual_emphasis" in signal_types
    assert "punctuation_damage" in signal_types
    assert "non_ascii_glyph" in signal_types
    assert "encoding_loss" in signal_types
