from __future__ import annotations

from src.reporting.text_unit_builders import (
    build_canonical_conversation_text,
    build_header_body_text,
    build_indexed_text_unit,
    build_timestamped_speaker_text,
)


def test_build_indexed_text_unit_shapes_unit_id_and_fields() -> None:
    unit = build_indexed_text_unit(
        source_id="source:test",
        source_type="demo_source",
        index="p1",
        text="hello",
    )

    assert unit.unit_id == "source:test:p1"
    assert unit.source_id == "source:test"
    assert unit.source_type == "demo_source"
    assert unit.text == "hello"


def test_build_timestamped_speaker_text_and_header_body_text_are_stable() -> None:
    speaker_line = build_timestamped_speaker_text(
        ts="2026-03-31T00:00:00Z",
        speaker="Alice",
        text="Hello",
    )
    header_body = build_header_body_text(
        header="[Firefox] Example",
        body="Body text",
    )

    assert speaker_line == "[2026-03-31T00:00:00Z] Alice: Hello"
    assert header_body == "[Firefox] Example\nBody text"


def test_build_canonical_conversation_text_shapes_generic_context_reply_and_speaker() -> None:
    text = build_canonical_conversation_text(
        text="What is distllm?",
        speaker="alice",
        reply_to="Earlier message",
        context=("Distributed systems discussion", "Model routing"),
    )

    assert text == (
        "[context] Distributed systems discussion\n"
        "[context] Model routing\n"
        "[reply_to] Earlier message\n"
        "alice:\n"
        "Q: What is distllm?"
    )


def test_build_canonical_conversation_text_marks_speakerless_questions_as_qa() -> None:
    text = build_canonical_conversation_text(text="What is distllm?")

    assert text == "Q: What is distllm?"
