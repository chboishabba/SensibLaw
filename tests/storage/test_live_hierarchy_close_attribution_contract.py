from __future__ import annotations

import runpy
from pathlib import Path

import pytest

from src.pnf.numeric_hyperfabric import RegionKind
from src.policy.live_hierarchy_close_attribution import _is_region_close_update, _parse_kinds


def test_hierarchy_kind_selector_accepts_names_and_ids() -> None:
    assert _parse_kinds("PARAGRAPH,5,document") == (
        RegionKind.PARAGRAPH,
        RegionKind.ADAPTIVE_BLOCK,
        RegionKind.DOCUMENT,
    )


def test_hierarchy_kind_selector_rejects_sentence() -> None:
    with pytest.raises(ValueError, match="must not select SENTENCE"):
        _parse_kinds("sentence")


def test_hierarchy_probe_matches_only_canonical_close_shape() -> None:
    assert _is_region_close_update(
        """
        UPDATE execution.semantic_pnf_region
           SET closure_state = %s,
               graph_revision = %s,
               closed_at = CURRENT_TIMESTAMP
         WHERE region_id = %s
        """
    )
    assert not _is_region_close_update(
        "UPDATE execution.semantic_pnf_region SET closure_state = %s WHERE region_id = %s"
    )


def test_hierarchy_attribution_source_pins_nested_sql_and_support() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (
        root / "src" / "policy" / "live_hierarchy_close_attribution.py"
    ).read_text(encoding="utf-8")
    assert "store._close_parent_interface" in source
    assert "EXPLAIN (ANALYZE, BUFFERS, WAL, VERBOSE, SETTINGS, FORMAT JSON)" in source
    assert "FROM pg_stat_statements" in source
    assert "query NOT ILIKE '%%pg_stat_statements%%'" in source
    assert "child.parent_region_id = %s" in source
    assert "child_interface_cardinality" in source
    assert "nested_statement_deltas" in source


def test_hierarchy_probe_is_wired_only_as_opt_in_diagnostic() -> None:
    root = Path(__file__).resolve().parents[2]
    hot_path = (
        root / "src" / "policy" / "closure_hot_path_execution.py"
    ).read_text(encoding="utf-8")
    source = (
        root / "src" / "policy" / "live_hierarchy_close_attribution.py"
    ).read_text(encoding="utf-8")
    assert "install_live_hierarchy_close_attribution()" in hot_path
    assert 'os.environ.get(_KINDS_ENV, "").strip()' in source
    assert "if not raw_kinds:" in source
    assert "return False" in source


def test_hierarchy_summary_warns_nested_times_are_not_additive() -> None:
    root = Path(__file__).resolve().parents[2]
    namespace = runpy.run_path(
        str(root / "scripts" / "summarize_live_hierarchy_close_attribution.py")
    )
    summary = namespace["summarize"](
        [
            {
                "selection": {
                    "region_kind": int(RegionKind.PARAGRAPH),
                    "region_kind_name": "PARAGRAPH",
                    "per_kind_ordinal": 1,
                },
                "preclose": {"region_id": 10},
                "hierarchy_support": {
                    "child_count": 2,
                    "child_interface_count": 2,
                    "child_interface_cardinality": 8,
                    "child_unresolved_count": 3,
                    "child_export_count_by_target_kind": {"1": 5},
                },
                "close_metrics": {
                    "execution_time_ms": 12.5,
                    "shared_hit_blocks": 7,
                    "shared_read_blocks": 0,
                    "temp_read_blocks": 0,
                    "temp_written_blocks": 0,
                    "wal_bytes": 128,
                },
                "nested_statement_deltas": [
                    {"query_id": 1, "query": "SELECT 1", "calls": 1, "total_exec_ms": 4.0}
                ],
            }
        ],
        top_statements=3,
    )
    assert summary["records"][0]["nested_total_exec_ms"] == 4.0
    assert "not an additive wall-time decomposition" in summary["semantics"]
