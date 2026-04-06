from src.ingestion.media_adapter import (
    MediaType,
    PdfPageMediaAdapter,
    SegmentKind,
    TextDocumentMediaAdapter,
    UnitKind,
    adapt_text_content,
    build_parsed_envelope,
    parse_canonical_text,
)


def test_adapt_text_content_emits_canonical_text():
    canonical = adapt_text_content(
        "Alpha `beta` gamma",
        provenance={"source": "unit-test"},
        segment_prefix="sample",
    )

    assert canonical.media_type == MediaType.TEXT.value
    assert canonical.text_id.startswith("sample:text:")
    assert canonical.text == "Alpha `beta` gamma"
    assert canonical.provenance["source"] == "unit-test"
    assert len(canonical.segments) == 1
    segment = canonical.segments[0]
    assert segment.text_id == canonical.text_id
    assert segment.segment_kind == SegmentKind.PARAGRAPH.value
    assert segment.anchors["char_range"] == [0, len(canonical.text)]
    assert segment.units[0].unit_kind == UnitKind.TEXT_RUN.value
    assert segment.units[0].segment_id == segment.segment_id
    assert segment.units[0].anchor_refs == {
        "text_id": canonical.text_id,
        "segment_id": segment.segment_id,
        "unit_id": segment.units[0].unit_id,
        "start_char": 0,
        "end_char": len(canonical.text),
        "order_index": 0,
        "media_type": MediaType.TEXT.value,
    }
    assert segment.start_char == 0
    assert segment.end_char == len(canonical.text)


def test_pdf_page_media_adapter_emits_heading_and_paragraph_segments():
    adapter = PdfPageMediaAdapter(
        source_artifact_ref="sample-doc",
        provenance={"source_path": "sample.pdf"},
    )

    canonical = adapter.adapt(
        [
            {"page": 1, "heading": "Heading 1", "text": "Alpha body"},
            {"page": 2, "heading": "Heading 2", "text": "Beta body"},
        ]
    )

    assert canonical.media_type == MediaType.TEXT.value
    assert canonical.text_id.startswith("sample-doc:text:")
    assert canonical.provenance["adapter"] == "pdf_page_media_adapter"
    assert canonical.provenance["source_path"] == "sample.pdf"
    assert canonical.text == "Heading 1\n\nAlpha body\n\nHeading 2\n\nBeta body"
    assert [segment.segment_kind for segment in canonical.segments] == [
        SegmentKind.HEADING.value,
        SegmentKind.PARAGRAPH.value,
        SegmentKind.HEADING.value,
        SegmentKind.PARAGRAPH.value,
    ]
    assert canonical.segments[1].metadata["page"] == 1
    assert canonical.segments[3].metadata["page"] == 2
    assert canonical.segments[0].anchors["page"] == 1
    assert canonical.segments[0].text_id == canonical.text_id
    assert canonical.segments[0].units[0].anchor_refs["page"] == 1
    assert canonical.segments[0].units[0].anchor_refs["order_index"] == 0

    envelope = build_parsed_envelope(canonical)
    assert envelope.envelope_id.startswith(f"{canonical.text_id}:envelope:")
    assert envelope.media_type == MediaType.TEXT.value
    assert envelope.canonical_text.text == canonical.text
    assert envelope.parse_profile == "structural_parse"
    assert envelope.ingest_receipt["text_id"] == canonical.text_id
    assert envelope.parse_receipt == {
        "parser_version": "canonical_text_parser_v1",
        "parse_profile": "structural_parse",
        "segment_count": 4,
        "unit_count": 4,
        "segment_kind_counts": {"heading": 2, "paragraph": 2},
        "unit_kind_counts": {"text_run": 4},
        "has_structure_graph": False,
        "warnings_count": 0,
        "inline_split_applied": False,
        "anchor_normalization_applied": True,
    }
    assert len(envelope.parsed_segments) == 4
    assert len(envelope.parsed_units) == 4


def test_parse_canonical_text_accepts_profile_override():
    canonical = adapt_text_content("Section 1\nAlpha must comply.", segment_prefix="policy")

    envelope = parse_canonical_text(
        canonical,
        parse_profile="normative_policy",
        ingest_receipt={"adapter": "text_document"},
    )

    assert envelope.parse_profile == "normative_policy"
    assert envelope.ingest_receipt["adapter"] == "text_document"
    assert envelope.parse_receipt["parse_profile"] == "normative_policy"
    assert envelope.parse_receipt["segment_kind_counts"] == {"paragraph": 1}
    assert envelope.parse_receipt["unit_kind_counts"] == {"text_run": 1}
    assert envelope.parsed_segments[0].segment_id == canonical.segments[0].segment_id
    assert envelope.parsed_units[0].segment_id == canonical.segments[0].segment_id
    assert envelope.segment_graph is None


def test_parse_canonical_text_can_attach_structure_graph():
    adapter = PdfPageMediaAdapter(source_artifact_ref="graph-doc")
    canonical = adapter.adapt([{"page": 1, "heading": "Section 1", "text": "Alpha body"}])

    envelope = parse_canonical_text(canonical, include_structure_graph=True)

    assert envelope.segment_graph is not None
    assert envelope.parse_receipt["has_structure_graph"] is True
    assert envelope.segment_graph.graph_id == f"{envelope.envelope_id}:segment_graph"
    assert envelope.to_dict()["segment_graph"]["graph_id"] == envelope.segment_graph.graph_id


def test_text_document_media_adapter_emits_canonical_text():
    adapter = TextDocumentMediaAdapter(
        source_artifact_ref="memo",
        provenance={"source_path": "memo.txt"},
    )

    canonical = adapter.adapt(
        {
            "body": "Alpha body",
            "provenance": {"publisher": "unit-test"},
        }
    )

    assert canonical.media_type == MediaType.TEXT.value
    assert canonical.text_id.startswith("memo:text:")
    assert canonical.text == "Alpha body"
    assert canonical.provenance["adapter"] == "text_document_media_adapter"
    assert canonical.provenance["source_path"] == "memo.txt"
    assert canonical.provenance["publisher"] == "unit-test"
    assert len(canonical.segments) == 1
    assert canonical.segments[0].segment_kind == SegmentKind.PARAGRAPH.value


def test_text_document_media_adapter_round_trips_into_parse_canonical_text():
    adapter = TextDocumentMediaAdapter(source_artifact_ref="inline")
    canonical = adapter.adapt("Alpha `beta` gamma [Doc](https://example.test)")

    envelope = parse_canonical_text(canonical)

    assert envelope.ingest_receipt["text_id"] == canonical.text_id
    assert envelope.parse_receipt == {
        "parser_version": "canonical_text_parser_v1",
        "parse_profile": "structural_parse",
        "segment_count": 1,
        "unit_count": 4,
        "segment_kind_counts": {"paragraph": 1},
        "unit_kind_counts": {
            "text_run": 2,
            "code_span": 1,
            "link": 1,
        },
        "has_structure_graph": False,
        "warnings_count": 0,
        "inline_split_applied": True,
        "anchor_normalization_applied": True,
    }
    assert [unit.unit_kind for unit in envelope.parsed_units] == [
        UnitKind.TEXT_RUN.value,
        UnitKind.CODE_SPAN.value,
        UnitKind.TEXT_RUN.value,
        UnitKind.LINK.value,
    ]
    assert envelope.parsed_units[0].anchor_refs == {
        "text_id": canonical.text_id,
        "segment_id": canonical.segments[0].segment_id,
        "unit_id": envelope.parsed_units[0].unit_id,
        "start_char": 0,
        "end_char": 6,
        "order_index": 0,
        "media_type": MediaType.TEXT.value,
    }
    assert envelope.parsed_units[1].text == "`beta`"
    assert envelope.parsed_units[1].segment_id == canonical.segments[0].segment_id
    assert envelope.parsed_units[1].anchor_refs["unit_id"] == envelope.parsed_units[1].unit_id
    assert envelope.parsed_units[1].anchor_refs["start_char"] == envelope.parsed_units[1].start_char
    assert envelope.parsed_units[1].anchor_refs["end_char"] == envelope.parsed_units[1].end_char
    assert envelope.parsed_units[3].metadata["target"] == "https://example.test"
