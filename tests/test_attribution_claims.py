from __future__ import annotations

from src.models.attribution_claims import (
    Attribution,
    AttributionType,
    CertaintyLevel,
    ExtractionMethod,
    ExtractionRecord,
    SourceEntity,
    SourceEntityType,
    attribution_id,
    authority_edges_for_attribution,
    authority_edges_for_extraction_record,
    extraction_record_id,
    source_entity_id,
    validate_attribution_chain,
)


def test_source_entity_id_is_deterministic() -> None:
    a = source_entity_id(
        SourceEntityType.WIKIPEDIA_ARTICLE,
        "George W. Bush",
        url="https://en.wikipedia.org/wiki/George_W._Bush",
        version_hash="abc123",
    )
    b = source_entity_id(
        SourceEntityType.WIKIPEDIA_ARTICLE,
        " george w.  bush ",
        url="https://en.wikipedia.org/wiki/George_W._Bush",
        version_hash="abc123",
    )
    assert a == b


def test_attribution_id_is_deterministic() -> None:
    sid = source_entity_id(SourceEntityType.NEWS_ARTICLE, "Example")
    a = attribution_id(
        claim_id="q1",
        attributed_actor_id="actor_bush",
        attribution_type=AttributionType.DIRECT_STATEMENT,
        source_entity_id_value=sid,
    )
    b = attribution_id(
        claim_id=" q1 ",
        attributed_actor_id=" actor_bush ",
        attribution_type=AttributionType.DIRECT_STATEMENT,
        source_entity_id_value=sid,
    )
    assert a == b


def test_validate_chain_detects_missing_parent() -> None:
    sid = source_entity_id(SourceEntityType.TRANSCRIPT, "Hearing")
    child = Attribution(
        id="a-child",
        claim_id="c1",
        attributed_actor_id="actor_x",
        attribution_type=AttributionType.REPORTED_STATEMENT,
        source_entity_id=sid,
        parent_attribution_id="a-missing",
    )
    try:
        validate_attribution_chain([child])
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "unknown parent_attribution_id" in str(exc)


def test_validate_chain_detects_cycle() -> None:
    sid = source_entity_id(SourceEntityType.TRANSCRIPT, "Hearing")
    a = Attribution(
        id="a1",
        claim_id="c1",
        attributed_actor_id="actor_x",
        attribution_type=AttributionType.REPORTED_STATEMENT,
        source_entity_id=sid,
        parent_attribution_id="a2",
    )
    b = Attribution(
        id="a2",
        claim_id="c1",
        attributed_actor_id="actor_y",
        attribution_type=AttributionType.REPORTED_STATEMENT,
        source_entity_id=sid,
        parent_attribution_id="a1",
    )
    try:
        validate_attribution_chain([a, b])
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "circular attribution chain" in str(exc)


def test_authority_edges_include_expected_predicates() -> None:
    sid = source_entity_id(SourceEntityType.COURT_OPINION, "Case X")
    aid = attribution_id(
        claim_id="claim-1",
        attributed_actor_id="actor_judge",
        attribution_type=AttributionType.EDITORIAL_SUMMARY,
        source_entity_id_value=sid,
        reporting_actor_id="actor_reporter",
    )
    attr = Attribution(
        id=aid,
        claim_id="claim-1",
        attributed_actor_id="actor_judge",
        attribution_type=AttributionType.EDITORIAL_SUMMARY,
        source_entity_id=sid,
        reporting_actor_id="actor_reporter",
        certainty_level=CertaintyLevel.IMPLICIT,
        extraction_method=ExtractionMethod.SUMMARY,
    )
    edges = authority_edges_for_attribution(attr)
    preds = {e.predicate for e in edges}
    assert {"attributed_by", "attributed_actor", "source_entity", "reporting_actor"} <= preds


def test_extraction_record_edges_shape() -> None:
    sid = source_entity_id(SourceEntityType.DATASET, "Dataset 1")
    rec = ExtractionRecord(
        id=extraction_record_id(
            source_entity_id_value=sid,
            parser_version="wiki_timeline_aoo_extract@v1",
            extraction_timestamp="2026-02-13T00:00:00Z",
        ),
        source_entity_id=sid,
        parser_version="wiki_timeline_aoo_extract@v1",
        extraction_timestamp="2026-02-13T00:00:00Z",
        confidence_score=0.95,
    )
    edges = authority_edges_for_extraction_record(rec)
    preds = {e.predicate for e in edges}
    assert preds == {"source_entity", "parser_version", "extracted_at"}


def test_source_entity_dataclass_fields() -> None:
    sid = source_entity_id(SourceEntityType.SPEECH, "Speech A")
    entity = SourceEntity(
        id=sid,
        type=SourceEntityType.SPEECH,
        title="Speech A",
        publication_date="2001-09-20",
        publisher="White House",
        url="https://example.test/speech",
        version_hash="v1",
    )
    assert entity.id == sid
    assert entity.type == SourceEntityType.SPEECH
