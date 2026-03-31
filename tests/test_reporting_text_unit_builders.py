from __future__ import annotations

from src.reporting.text_unit_builders import (
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
