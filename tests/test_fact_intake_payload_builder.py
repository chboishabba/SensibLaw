from __future__ import annotations

from src.fact_intake.payload_builder import (
    build_excerpt_row,
    build_fact_candidate_row,
    build_fact_intake_payload,
    build_fact_intake_run,
    build_source_rows,
    build_statement_row,
    ensure_event_source_row,
)


def test_build_fact_intake_run_is_deterministic() -> None:
    run = build_fact_intake_run(
        run_kind="transcript_fact_intake_run",
        semantic_run_id="semantic:1",
        per_event=[{"event_id": "e1"}],
        source_documents=[{"sourceDocumentId": "doc:1"}],
        source_label="transcript_semantic:semantic:1",
        notes="demo",
    )
    assert run["run_id"].startswith("factrun:")
    assert run["contract_version"] == "fact.intake.bundle.v1"
    assert run["mary_projection_version"] == "mary.fact_workflow.v1"


def test_build_source_rows_and_event_fallback_preserve_ordering() -> None:
    sources, source_map = build_source_rows(
        run_id="factrun:1",
        semantic_run_id="semantic:1",
        source_documents=[
            {
                "sourceDocumentId": "doc:1",
                "sourceType": "transcript_file",
                "title": "Doc 1",
                "text": "hello",
            }
        ],
        default_source_type="transcript_file",
        lexical_mode_for=lambda source_type: "chat_archive" if source_type == "transcript_file" else None,
    )
    source_id = ensure_event_source_row(
        sources=sources,
        source_map=source_map,
        run_id="factrun:1",
        semantic_run_id="semantic:1",
        source_document_id="doc:2",
        source_type="transcript_file",
        source_text="world",
        lexical_mode_for=lambda source_type: "chat_archive" if source_type == "transcript_file" else None,
        source_document_value="doc:2",
    )
    assert len(sources) == 2
    assert source_id == sources[1]["source_id"]
    assert sources[1]["source_order"] == 2


def test_build_excerpt_statement_fact_candidate_rows_share_provenance_shape() -> None:
    excerpt = build_excerpt_row(
        run_id="factrun:1",
        semantic_run_id="semantic:1",
        event_id="e1",
        source_id="src:1",
        excerpt_order=1,
        excerpt_text="hello",
        char_start=0,
        char_end=5,
        anchor_label="e1",
        extra_provenance={"section": "Intro"},
    )
    statement = build_statement_row(
        run_id="factrun:1",
        semantic_run_id="semantic:1",
        event_id="e1",
        excerpt_id=excerpt["excerpt_id"],
        statement_text="hello",
        statement_role="transcript_statement",
        chronology_hint=None,
        extra_provenance={"section": "Intro"},
    )
    fact = build_fact_candidate_row(
        run_id="factrun:1",
        semantic_run_id="semantic:1",
        event_id="e1",
        canonical_label="hello",
        fact_text="hello",
        fact_type="transcript_statement_capture",
        candidate_status="candidate",
        chronology_sort_key=None,
        chronology_label="e1",
        primary_statement_id=statement["statement_id"],
        extra_provenance={"section": "Intro"},
    )
    assert excerpt["provenance"]["section"] == "Intro"
    assert statement["provenance"]["section"] == "Intro"
    assert fact["provenance"]["section"] == "Intro"


def test_build_fact_intake_payload_shapes_shared_payload() -> None:
    payload = build_fact_intake_payload(
        run={"run_id": "factrun:1"},
        sources=[{"source_id": "src:1"}],
        excerpts=[{"excerpt_id": "excerpt:1"}],
        statements=[{"statement_id": "statement:1"}],
        observations=[{"observation_id": "obs:1"}],
        fact_candidates=[{"fact_id": "fact:1"}],
    )
    assert payload["run"]["run_id"] == "factrun:1"
    assert payload["contestations"] == []
    assert payload["reviews"] == []
