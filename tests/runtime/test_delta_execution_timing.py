from __future__ import annotations

from src.runtime.delta_execution_timing import (
    DELTA_EXECUTION_TIMING_REF,
    DeltaExecutionTimingLedger,
    DeltaTimingStage,
)


def test_disabled_ledger_has_zero_observation_tax_surface() -> None:
    ledger = DeltaExecutionTimingLedger(enabled=False)
    with ledger.measure(
        stage=DeltaTimingStage.LOCAL_REDUCER,
        owner_ref="owner:test",
        fibre_ref="fibre:1",
    ):
        pass
    assert ledger.observations == []
    receipt = ledger.to_dict()
    assert receipt["enabled"] is False
    assert receipt["semantic_authority_effect"] == "none"
    assert receipt["semantic_identity_effect"] == "none"


def test_stage_and_owner_totals_are_native_nanoseconds() -> None:
    ledger = DeltaExecutionTimingLedger(enabled=True)
    ledger.record(
        stage=DeltaTimingStage.SOURCE_DELTA,
        owner_ref="owner:a",
        fibre_ref="fibre:1",
        elapsed_ns=7,
        input_work_units=2,
        output_work_units=3,
    )
    ledger.record(
        stage=DeltaTimingStage.LOCAL_REDUCER,
        owner_ref="owner:a",
        fibre_ref="fibre:1",
        elapsed_ns=11,
    )
    ledger.record(
        stage=DeltaTimingStage.LOCAL_REDUCER,
        owner_ref="owner:b",
        fibre_ref="fibre:2",
        elapsed_ns=13,
    )
    assert ledger.stage_totals_ns()["source_delta"] == 7
    assert ledger.stage_totals_ns()["local_reducer"] == 24
    assert ledger.owner_totals_ns() == {"owner:a": 18, "owner:b": 13}
    assert ledger.to_dict()["contract_ref"] == DELTA_EXECUTION_TIMING_REF


def test_all_reusable_delta_stages_are_explicit() -> None:
    assert [stage.value for stage in DeltaTimingStage] == [
        "source_delta",
        "projection_atoms",
        "affected_keys",
        "local_reducer",
        "authority_publication",
    ]
