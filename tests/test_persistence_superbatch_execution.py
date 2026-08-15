from __future__ import annotations

from types import SimpleNamespace

from src.storage.postgres import work_conserving_graph_batching as graph_batching
from src.storage.postgres import work_conserving_resolution_batching as resolution_batching
from src.storage.postgres.work_conserving_stage import StagePayload


class _Cursor:
    def __init__(self) -> None:
        self.executed: list[tuple[str, object]] = []

    def execute(self, sql: str, params: object = None) -> None:
        self.executed.append((sql, params))


def test_graph_batch_returns_identities_before_physical_flush(monkeypatch) -> None:
    runtime = SimpleNamespace()
    cursor = _Cursor()
    monkeypatch.setattr(graph_batching, "_runtime", lambda: runtime)
    monkeypatch.setenv("SENSIBLAW_PERSISTENCE_GRAPH_BATCH_PAYLOADS", "100")
    factor_payload = StagePayload("factor", texts=("factor:1", "document:1", "norm"))
    monkeypatch.setattr(
        graph_batching,
        "_factor_payloads",
        lambda **_kwargs: ([factor_payload], {"factor:1": "revision:1"}),
    )

    revisions = graph_batching.persist_pnf_graph_batched(
        cursor,
        document_ref="document:1",
        graph={
            "graph_ref": "graph:1",
            "factors": ({"closure_state": "closed"},),
        },
    )

    assert revisions == {"factor:1": "revision:1"}
    assert cursor.executed == []
    assert len(runtime._graph_batch_payloads) == 2  # header + factor


def test_graph_batch_deduplicates_repeated_factor_payloads(monkeypatch) -> None:
    runtime = SimpleNamespace()
    cursor = _Cursor()
    monkeypatch.setattr(graph_batching, "_runtime", lambda: runtime)
    monkeypatch.setenv("SENSIBLAW_PERSISTENCE_GRAPH_BATCH_PAYLOADS", "100")
    factor_payload = StagePayload("factor", texts=("factor:1", "document:1", "norm"))
    monkeypatch.setattr(
        graph_batching,
        "_factor_payloads",
        lambda **_kwargs: ([factor_payload], {"factor:1": "revision:1"}),
    )

    graph = {
        "graph_ref": "graph:1",
        "factors": ({"closure_state": "closed"},),
    }
    graph_batching.persist_pnf_graph_batched(cursor, document_ref="document:1", graph=graph)
    graph_batching.persist_pnf_graph_batched(cursor, document_ref="document:1", graph=graph)

    assert runtime._graph_batch_payloads.count(factor_payload) == 1
    assert sum(row.row_kind_ref == "graph_header" for row in runtime._graph_batch_payloads) == 1


def test_resolution_batch_flushes_graph_before_authority(monkeypatch) -> None:
    runtime = SimpleNamespace(
        _resolution_batch_payloads=[
            StagePayload(
                "demand",
                texts=("demand:1", "factor:1", "revision:1", "norm", None, "scope", "default", "open"),
            )
        ],
        _resolution_batch_payload_set=set(),
        _resolution_batch_cursor=None,
    )
    runtime._resolution_batch_payload_set.update(runtime._resolution_batch_payloads)
    cursor = _Cursor()
    runtime._resolution_batch_cursor = cursor
    events: list[str] = []
    monkeypatch.setattr(resolution_batching, "_runtime", lambda: runtime)
    monkeypatch.setattr(
        resolution_batching,
        "flush_graph_batch",
        lambda _cursor: events.append("graph"),
    )
    monkeypatch.setattr(
        resolution_batching,
        "observable_stage_payloads",
        lambda *_args, **_kwargs: events.append("stage") or "stage:resolution",
    )
    monkeypatch.setattr(
        resolution_batching,
        "observable_complete_stage",
        lambda *_args, **_kwargs: events.append("complete"),
    )

    resolution_batching.flush_resolution_batch(cursor)

    assert events[0:2] == ["graph", "stage"]
    assert events[-1] == "complete"
    assert len(cursor.executed) == 14
    assert runtime._resolution_batch_payloads == []
    assert runtime.resolution_superbatches_flushed == 1


def test_resolution_batch_returns_demand_refs_without_sql(monkeypatch) -> None:
    runtime = SimpleNamespace()
    cursor = _Cursor()
    monkeypatch.setattr(resolution_batching, "_runtime", lambda: runtime)
    monkeypatch.setenv("SENSIBLAW_PERSISTENCE_RESOLUTION_BATCH_PAYLOADS", "100")
    monkeypatch.setattr(
        resolution_batching,
        "_resolution_payloads",
        lambda **_kwargs: [StagePayload("demand", texts=("demand:2",))],
    )

    refs = resolution_batching.persist_resolution_batched(
        cursor,
        factor_revisions={},
        demands=({"demand_ref": "demand:2"},),
        evidence=(),
        meets=(),
        refinements=(),
    )

    assert refs == ("demand:2",)
    assert cursor.executed == []
