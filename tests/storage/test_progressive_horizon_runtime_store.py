from __future__ import annotations

from src.storage.postgres.progressive_horizon_runtime_store import (
    ProgressiveHorizonRuntimeStore,
)


def _store() -> ProgressiveHorizonRuntimeStore:
    return ProgressiveHorizonRuntimeStore("postgresql://unused/test")


def test_h6_is_skipped_when_h3_has_no_residual(monkeypatch) -> None:
    store = _store()
    events: list[str] = []
    monkeypatch.setattr(
        store,
        "seed_h3_for_consumer",
        lambda **_kwargs: events.append("seed_h3") or 4,
    )
    monkeypatch.setattr(
        store,
        "advance_horizon_for_consumer",
        lambda **_kwargs: events.append("advance_h3") or 0,
    )
    monkeypatch.setattr(
        store,
        "process_h6_for_consumer",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("H6 must not run without H3 residual work")
        ),
    )

    receipt = store.process_progressive_horizons(
        run_id=1,
        document_id=2,
        consumer_ref="consumer:test",
        query_ref="query:test",
    )

    assert events == ["seed_h3", "advance_h3"]
    assert receipt.seeded_h3 == 4
    assert receipt.h6_residual_work == 0
    assert receipt.inserted_h6_evidence == 0
    assert receipt.h9_residual_work == 0


def test_h9_planning_is_skipped_when_h6_has_no_residual(monkeypatch) -> None:
    store = _store()
    events: list[str] = []
    monkeypatch.setattr(store, "seed_h3_for_consumer", lambda **_kwargs: 3)
    monkeypatch.setattr(store, "advance_horizon_for_consumer", lambda **_kwargs: 2)
    monkeypatch.setattr(
        store,
        "process_h6_for_consumer",
        lambda **_kwargs: events.append("h6") or (7, 0),
    )
    monkeypatch.setattr(
        store,
        "compile_and_plan_world_axis_contracts",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("H9 planning must not run without H6 residual work")
        ),
    )

    receipt = store.process_progressive_horizons(
        run_id=1,
        document_id=2,
        consumer_ref="consumer:test",
        query_ref="query:test",
        plan_h9=True,
    )

    assert events == ["h6"]
    assert receipt.inserted_h6_evidence == 7
    assert receipt.h9_residual_work == 0
    assert receipt.planned_external_work == 0


def test_h9_planning_runs_only_for_explicit_residual_and_never_provider_io(
    monkeypatch,
) -> None:
    store = _store()
    events: list[str] = []
    monkeypatch.setattr(store, "seed_h3_for_consumer", lambda **_kwargs: 5)
    monkeypatch.setattr(store, "advance_horizon_for_consumer", lambda **_kwargs: 3)
    monkeypatch.setattr(store, "process_h6_for_consumer", lambda **_kwargs: (11, 2))
    monkeypatch.setattr(
        store,
        "compile_and_plan_world_axis_contracts",
        lambda **_kwargs: events.append("plan_h9") or (2, 1),
    )
    monkeypatch.setattr(
        store,
        "claim_external_provider_batch",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("progressive horizon execution must not perform provider I/O")
        ),
    )

    receipt = store.process_progressive_horizons(
        run_id=1,
        document_id=2,
        consumer_ref="consumer:test",
        query_ref="query:test",
        plan_h9=True,
    )

    assert events == ["plan_h9"]
    assert receipt.h6_residual_work == 3
    assert receipt.h9_residual_work == 2
    assert receipt.compiled_external_needs == 2
    assert receipt.planned_external_work == 1
    assert receipt.provider_io_performed is False


def test_h9_planning_requires_explicit_opt_in(monkeypatch) -> None:
    store = _store()
    monkeypatch.setattr(store, "seed_h3_for_consumer", lambda **_kwargs: 1)
    monkeypatch.setattr(store, "advance_horizon_for_consumer", lambda **_kwargs: 1)
    monkeypatch.setattr(store, "process_h6_for_consumer", lambda **_kwargs: (1, 1))
    monkeypatch.setattr(
        store,
        "compile_and_plan_world_axis_contracts",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("H9 planning requires explicit plan_h9=True")
        ),
    )

    receipt = store.process_progressive_horizons(
        run_id=1,
        document_id=2,
        consumer_ref="consumer:test",
        query_ref="query:test",
    )

    assert receipt.h9_residual_work == 1
    assert receipt.compiled_external_needs == 0
    assert receipt.provider_io_performed is False
