from __future__ import annotations

from sensiblaw.interfaces import build_canonical_conversation_text
from src.reporting.text_unit_builders import build_canonical_conversation_text as build_internal_canonical_conversation_text


def test_text_adapter_matches_internal_builder_contract() -> None:
    assert build_canonical_conversation_text(
        text="hello",
        speaker="alice",
        context=("prior note",),
    ) == build_internal_canonical_conversation_text(
        text="hello",
        speaker="alice",
        context=("prior note",),
    )


def test_text_adapter_rejects_blank_text() -> None:
    try:
        build_canonical_conversation_text(text="   ")
    except ValueError as exc:
        assert "text must not be blank" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("expected ValueError for blank text")
