from src.pnf.numeric_hyperfabric import RegionKind
from src.storage.postgres.hierarchy_close_admission_pushdown import (
    CURRENT_GROUP_SELECT_SQL,
    PUSHDOWN_GROUP_SELECT_SQL,
    PUSHDOWN_INSERT_SQL,
    ParentLookupPushdownAudit,
    child_interface_ids_for_parent,
    concentration_profile,
)


def test_candidate_pushdown_uses_parent_export_admission_before_grouping() -> None:
    assert "EXISTS (" not in CURRENT_GROUP_SELECT_SQL
    assert "GROUP BY" in CURRENT_GROUP_SELECT_SQL

    assert "FROM execution.semantic_pnf_interface_lookup AS lookup" in PUSHDOWN_GROUP_SELECT_SQL
    assert "lookup.interface_id = ANY(%s)" in PUSHDOWN_GROUP_SELECT_SQL
    assert "EXISTS (" in PUSHDOWN_GROUP_SELECT_SQL
    assert "parent_export.interface_id = %s" in PUSHDOWN_GROUP_SELECT_SQL
    assert "parent_export.target_kind = lookup.target_kind" in PUSHDOWN_GROUP_SELECT_SQL
    assert "parent_export.target_id = lookup.target_id" in PUSHDOWN_GROUP_SELECT_SQL
    assert PUSHDOWN_GROUP_SELECT_SQL.index("AND EXISTS (") < PUSHDOWN_GROUP_SELECT_SQL.index(
        "GROUP BY"
    )
    assert "min(lookup.rank)" in PUSHDOWN_GROUP_SELECT_SQL

    assert "INSERT INTO execution.semantic_pnf_interface_lookup" in PUSHDOWN_INSERT_SQL
    assert "ON CONFLICT DO NOTHING" in PUSHDOWN_INSERT_SQL


def test_child_discovery_uses_typed_execution_window_exclusion() -> None:
    class Cursor:
        def __init__(self) -> None:
            self.parameters = None

        def execute(self, sql, parameters) -> None:
            self.parameters = parameters
            assert "child_region.region_kind <> %s" in sql

        def fetchall(self):
            return [(11,), (12,)]

    cursor = Cursor()
    assert child_interface_ids_for_parent(cursor, parent_interface_id=7) == (11, 12)
    assert cursor.parameters == (7, int(RegionKind.EXECUTION_WINDOW))


def test_document_root_forensic_receipt_matches_observed_reduction() -> None:
    receipt = ParentLookupPushdownAudit(
        parent_interface_id=1,
        child_interface_count=36,
        source_rows=358_965,
        admitted_source_rows=125_933,
        grouped_candidate_rows=42_836,
        stored_parent_rows=42_836,
        missing_candidate_rows=0,
        excess_candidate_rows=0,
    )
    assert receipt.exact_parity
    assert receipt.grouping_input_reduction is not None
    assert round(receipt.grouping_input_reduction, 3) == 0.649
    assert round(receipt.source_to_output_amplification or 0.0, 2) == 8.38
    assert round(receipt.admitted_to_output_amplification or 0.0, 2) == 2.94


def test_pushdown_parity_fails_closed_on_missing_or_excess_rows() -> None:
    missing = ParentLookupPushdownAudit(
        parent_interface_id=1,
        child_interface_count=1,
        source_rows=10,
        admitted_source_rows=5,
        grouped_candidate_rows=4,
        stored_parent_rows=5,
        missing_candidate_rows=1,
        excess_candidate_rows=0,
    )
    excess = ParentLookupPushdownAudit(
        parent_interface_id=1,
        child_interface_count=1,
        source_rows=10,
        admitted_source_rows=5,
        grouped_candidate_rows=6,
        stored_parent_rows=5,
        missing_candidate_rows=0,
        excess_candidate_rows=1,
    )
    assert not missing.exact_parity
    assert not excess.exact_parity


def test_concentration_profile_records_heavy_tail_without_mean_smearing() -> None:
    points = concentration_profile([424, 100, 90, 80, 70, 60, 50, 40, 35, 28, 23])
    assert points[0].k == 1
    assert points[0].fraction == 424 / 1000
    assert points[1].k == 10
    assert points[1].fraction == 977 / 1000


def test_concentration_profile_rejects_negative_work() -> None:
    try:
        concentration_profile([1, -1])
    except ValueError as exc:
        assert "non-negative" in str(exc)
    else:
        raise AssertionError("negative workload must fail closed")
