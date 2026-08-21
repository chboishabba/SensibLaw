from __future__ import annotations

from pathlib import Path

from src.policy.region_close_support_vector import (
    REGION_CLOSE_SUPPORT_VECTOR_REF,
    capture_region_close_support_vector,
)


class _FakeCursor:
    def __init__(self) -> None:
        self.query = ""
        self.params = None

    def execute(self, query, params=None):
        self.query = str(query)
        self.params = params

    def fetchone(self):
        # Fifteen SQL counts.  Left/right counts are deliberately both nonzero
        # so the derived adjacency side support is exactly two.
        return (100, 70, 60, 20, 55, 12, 9, 8, 14, 3, 2, 1, 4, 7, 5)


def _preclose() -> dict[str, object]:
    return {
        "run_ref": "run:test",
        "document_ref": "document:test",
        "region_id": 42,
        "parent_region_id": 7,
        "region_kind": 1,
        "start_char": 100,
        "end_char": 120,
    }


def test_support_vector_separates_local_support_from_document_population() -> None:
    cursor = _FakeCursor()

    vector = capture_region_close_support_vector(cursor, preclose=_preclose())

    assert vector["contract_ref"] == REGION_CLOSE_SUPPORT_VECTOR_REF
    assert vector["document_region_count"] == 100
    assert vector["same_parent_closed_sibling_count"] == 8
    assert vector["local_token_count"] == 14
    assert vector["local_pronoun_token_count"] == 3
    assert vector["adjacent_candidate_side_count"] == 2


def test_support_query_tracks_actual_adjacent_and_anaphor_trigger_supports() -> None:
    cursor = _FakeCursor()

    capture_region_close_support_vector(cursor, preclose=_preclose())

    assert "parent_region_id IS NOT DISTINCT FROM %s" in cursor.query
    assert "closure_state IN (2,3)" in cursor.query
    assert "token.pos_symbol_id=constant.pronoun_pos_symbol_id" in cursor.query
    assert "semantic_pnf_sentence_region" in cursor.query
    assert "semantic_pnf_anaphor_projection_constant" in cursor.query


def test_live_close_probe_records_support_before_measured_close() -> None:
    source = Path("src/policy/live_region_close_explain.py").read_text()
    support = source.index("support_vector = capture_region_close_support_vector")
    proxy = source.index("proxy = _RegionCloseExplainCursor")
    assert support < proxy
    assert '"semantic_support_vector": support_vector' in source
    assert "sensiblaw.live-region-close-explain.v0_2" in source


def test_summary_exposes_local_and_accumulated_axes_separately() -> None:
    source = Path("scripts/summarize_live_region_close_explains.py").read_text()
    assert '"local_boundary_support"' in source
    assert '"local_anaphor_support"' in source
    assert '"document_regions"' in source
    assert '"document_interfaces"' in source
    assert "sensiblaw.live-region-close-explain-summary.v0_2" in source
