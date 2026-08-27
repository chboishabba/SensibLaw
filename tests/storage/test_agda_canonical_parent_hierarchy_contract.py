from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PLANNER = ROOT / "src/storage/postgres/numeric_hierarchy_planner.py"


def _source() -> str:
    return PLANNER.read_text(encoding="utf-8")


def _helper_body(source: str) -> str:
    start = source.index("def _close_canonical_parent_interface(")
    end = source.index("\ndef _refresh_reductive_measure(", start)
    return source[start:end]


def test_strict_hierarchy_uses_canonical_parent_closer() -> None:
    source = _source()
    materialize_start = source.index("def materialize_numeric_document_hierarchy(")
    materialize = source[materialize_start:]

    assert "_close_canonical_parent_interface(" in materialize
    assert "store._close_parent_interface(" not in materialize


def test_parent_shell_does_not_copy_exports_or_lookups() -> None:
    helper = _helper_body(_source())

    assert "INSERT INTO execution.semantic_pnf_interface_export" not in helper
    assert "INSERT INTO execution.semantic_pnf_interface_lookup" not in helper
    assert "semantic_pnf_parent_delta_projection" in helper
    assert "rebuild_numeric_pnf_parent_frontier" in helper


def test_parent_shell_preserves_digest_coordinates() -> None:
    helper = _helper_body(_source())

    for coordinate in (
        "region_id,",
        "graph_revision,",
        "child_interface_ids,",
        "compressed.node_count,",
        "compressed.edge_count,",
        "compressed.interface_cardinality,",
        "compressed.unresolved_count,",
    ):
        assert coordinate in helper


def test_canonical_reduction_precedes_return() -> None:
    helper = _helper_body(_source())

    reducer = helper.rindex("rebuild_numeric_pnf_parent_frontier")
    returned = helper.rindex("return interface_id")
    assert reducer < returned


def test_parent_lookup_remains_reducer_owned() -> None:
    helper = _helper_body(_source())

    # DASHI ParentInterfaceReduction: lookup is a searchable projection of an
    # admitted parent export, never independent child evidence copied upward.
    assert "provisional parent" in helper
    assert "Sole parent-boundary authority" in helper
