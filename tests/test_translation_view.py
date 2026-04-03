from __future__ import annotations

import pytest

from src.sources.translation_view import build_translation_view


def test_translation_view_consistency_bounds() -> None:
    view = build_translation_view(
        source_id="legislation.gov.uk:1:en",
        target_language="fr",
        translator="human",
        consistency_score=0.85,
        drift_flag=False,
    )
    assert view["status"] == "translation"


def test_translation_view_score_range() -> None:
    with pytest.raises(ValueError):
        build_translation_view(
            source_id="x",
            target_language="es",
            translator="ai",
            consistency_score=1.5,
            drift_flag=True,
        )
