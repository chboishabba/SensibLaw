from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

from src.ingestion.media_adapter import TextDocumentMediaAdapter, build_parsed_envelope
from src.sensiblaw.interfaces import (
    PredicateAtom,
    QualifierState,
    TypedArg,
    WrapperState,
    project_event_text_to_predicate_atoms,
)


def _canonical(text: str):
    canonical = TextDocumentMediaAdapter().adapt(text)
    parsed = build_parsed_envelope(canonical)
    return canonical, parsed


def test_market_news_projector_rejects_unsupported_profile() -> None:
    canonical, parsed = _canonical("Plain text")
    try:
        project_event_text_to_predicate_atoms(canonical, parsed, {}, extraction_profile="other")
    except ValueError as exc:
        assert "unsupported extraction_profile" in str(exc)
    else:  # pragma: no cover - must raise
        raise AssertionError("expected ValueError")


def test_market_news_projector_returns_empty_for_blank_text() -> None:
    canonical, parsed = _canonical("")
    assert project_event_text_to_predicate_atoms(canonical, parsed, {"provider": "newsapi"}) == []


def test_market_news_projector_wraps_shared_reducer_atoms_without_domain_recovery() -> None:
    canonical, parsed = _canonical("Example text")
    shared_atom = PredicateAtom(
        predicate="signals",
        structural_signature="predicate=signals|subject=fed|object=inflation_risk",
        roles={
            "subject": TypedArg(value="Fed", status="bound"),
            "object": TypedArg(value="inflation risk", status="bound"),
        },
        qualifiers=QualifierState(polarity="negative"),
        wrapper=WrapperState(status="raw_shared_reducer", evidence_only=True),
        modifiers={"seed": "shared"},
        provenance=("seed:shared",),
        atom_id="seed-1",
        domain="generic",
    )
    with patch(
        'src.sensiblaw.interfaces.market_news_projector.collect_canonical_predicate_atoms',
        return_value=[shared_atom],
    ):
        projected = project_event_text_to_predicate_atoms(
            canonical,
            parsed,
            {"provider": "newsapi", "source_url": "https://example.test/shared"},
        )

    assert len(projected) == 1
    first = projected[0]
    assert first.predicate == "signals"
    assert first.roles["subject"].value == "Fed"
    assert first.roles["object"].value == "inflation risk"
    assert first.wrapper.status == "market_news_projection_candidate"
    assert first.wrapper.evidence_only is True
    assert first.domain == "market_news"
    assert first.modifiers["projection_mode"] == "shared_reducer_only"
    assert first.modifiers["provider"] == "newsapi"
    assert first.modifiers["candidate_status"] == "derived_candidate"
    assert f"text_id:{canonical.text_id}" in first.provenance
    assert f"envelope_id:{parsed.envelope_id}" in first.provenance
    assert f"projector:sensiblaw_market_news_projector_v2" in first.provenance


def test_market_news_projector_does_not_fabricate_when_shared_reducer_is_empty() -> None:
    canonical, parsed = _canonical("Fed signals inflation risk.")
    with patch(
        'src.sensiblaw.interfaces.market_news_projector.collect_canonical_predicate_atoms',
        return_value=[],
    ):
        projected = project_event_text_to_predicate_atoms(canonical, parsed, {"provider": "newsapi"})
    assert projected == []


def test_market_news_projector_is_importable_from_external_path_style() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root))
    try:
        from src.sensiblaw.interfaces import project_event_text_to_predicate_atoms as imported
    finally:
        sys.path.pop(0)

    canonical, parsed = _canonical("Example text")
    with patch(
        'src.sensiblaw.interfaces.market_news_projector.collect_canonical_predicate_atoms',
        return_value=[],
    ):
        projected = imported(canonical, parsed, {"provider": "newsapi"})
    assert projected == []
