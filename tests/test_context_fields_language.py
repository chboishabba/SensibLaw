from __future__ import annotations

from sensiblaw.context_render import BANNED_CAUSAL_TERMS, render_context_summary


def test_context_summary_neutral_language():
    payload = {"temp_c": 34.2, "humidity": 18}
    summary = render_context_summary("weather", payload)
    lowered = summary.lower()
    for term in BANNED_CAUSAL_TERMS:
        assert term not in lowered
    assert "no interpretation" in summary


def test_context_summary_handles_empty_payload():
    summary = render_context_summary("market")
    lowered = summary.lower()
    for term in BANNED_CAUSAL_TERMS:
        assert term not in lowered
    assert "no interpretation" in summary
