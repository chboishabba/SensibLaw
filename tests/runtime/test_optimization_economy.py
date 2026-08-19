from src.runtime.optimization_economy import (
    AmplificationReceipt,
    ArchitectureEconomy,
    OptimizationEconomyReceipt,
    ParetoState,
    RelationalWorkReceipt,
    RuntimeEconomy,
    compare_pareto,
    concentration_profile,
)


def _receipt(
    *,
    wall_ns: int = 100,
    historical_rows_examined: int = 1000,
    attempted_writes: int = 100,
    new_primitives: int = 1,
    duplicated_capabilities: int = 1,
    reused_capabilities: int = 4,
    retired: int = 0,
    parity: str = "parity:fixture-v1",
) -> OptimizationEconomyReceipt:
    return OptimizationEconomyReceipt(
        runtime=RuntimeEconomy(
            wall_ns=wall_ns,
            semantic_work_units=100,
            peak_rss_bytes=1000,
            io_units=100,
            reused_work_units=80,
            new_work_units=20,
            amplification=AmplificationReceipt(
                touched_semantic_rows=10,
                historical_rows_examined=historical_rows_examined,
                attempted_writes=attempted_writes,
                semantically_new_writes=10,
            ),
        ),
        architecture=ArchitectureEconomy(
            new_primitives=new_primitives,
            duplicated_capabilities=duplicated_capabilities,
            reused_capabilities=reused_capabilities,
            retired_compatibility_surfaces=retired,
        ),
        semantic_parity_ref=parity,
    )


def test_amplification_receipt_reports_history_and_write_ratios() -> None:
    receipt = AmplificationReceipt(
        touched_semantic_rows=20,
        historical_rows_examined=400_000,
        attempted_writes=10_000,
        semantically_new_writes=100,
    )
    assert receipt.history_read_amplification == 20_000
    assert receipt.write_amplification == 100


def test_relational_receipt_separates_scan_from_grouping_work() -> None:
    receipt = RelationalWorkReceipt(
        rows_scanned=358_965,
        rows_admitted=125_933,
        rows_grouped=125_933,
        rows_output=42_836,
        attempted_writes=42_836,
        committed_writes=42_836,
    )
    assert round(receipt.admission_selectivity or 0.0, 3) == 0.351
    assert round(receipt.grouping_input_reduction or 0.0, 3) == 0.649
    assert round(receipt.scan_amplification or 0.0, 2) == 8.38
    assert round(receipt.quotient_amplification or 0.0, 2) == 2.94
    assert receipt.write_amplification == 1.0


def test_zero_denominator_does_not_forge_finite_ratio() -> None:
    receipt = AmplificationReceipt(
        touched_semantic_rows=0,
        historical_rows_examined=1,
        attempted_writes=0,
        semantically_new_writes=0,
    )
    assert receipt.history_read_amplification is None
    assert receipt.write_amplification == 0.0


def test_architecture_economy_penalizes_new_authority_and_duplication() -> None:
    cheap = ArchitectureEconomy(new_primitives=1, reused_capabilities=5)
    expensive = ArchitectureEconomy(
        new_primitives=1,
        new_authority_surfaces=1,
        duplicated_capabilities=1,
        reused_capabilities=5,
    )
    assert expensive.novelty_burden() > cheap.novelty_burden()
    assert cheap.capability_reuse_ratio == 5 / 6


def test_pareto_improvement_can_be_faster_and_simpler() -> None:
    before = _receipt()
    after = _receipt(
        wall_ns=50,
        historical_rows_examined=100,
        attempted_writes=20,
        new_primitives=0,
        duplicated_capabilities=0,
        reused_capabilities=5,
        retired=2,
    )
    assert compare_pareto(before, after) is ParetoState.IMPROVEMENT


def test_pareto_comparison_is_unknown_without_common_parity_boundary() -> None:
    before = _receipt(parity="parity:a")
    after = _receipt(parity="parity:b")
    assert compare_pareto(before, after) is ParetoState.UNKNOWN


def test_speed_bought_with_new_authority_is_a_tradeoff_not_pareto_win() -> None:
    before = _receipt(new_primitives=0, duplicated_capabilities=0)
    after = _receipt(
        wall_ns=50,
        new_primitives=1,
        duplicated_capabilities=0,
    )
    assert compare_pareto(before, after) is ParetoState.TRADEOFF


def test_concentration_profile_keeps_hot_strata_visible() -> None:
    points = concentration_profile([424, 100, 90, 80, 70, 60, 50, 40, 35, 28, 23])
    assert points[0].k == 1
    assert points[0].fraction == 0.424
    assert points[1].k == 10
    assert points[1].fraction == 0.977
