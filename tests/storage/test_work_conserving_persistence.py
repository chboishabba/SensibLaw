from __future__ import annotations

from pathlib import Path

import pytest

from src.policy.algebra.revision_identity import factor_revision_ref
from src.storage.postgres import work_conserving_persistence as persistence
from src.storage.postgres import work_conserving_stage as stage


def _factor(*, factor_ref: str = "factor:1") -> dict[str, object]:
    return {
        "factor_ref": factor_ref,
        "factor_type": "predicate",
        "closure_state": "locally_closed",
        "alternatives": (
            {
                "alternative_ref": f"{factor_ref}:alternative:1",
                "type_ref": "mention",
                "value": {"mention_ref": "mention:1"},
                "authority_state": "candidate_only",
            },
        ),
        "residuals": ("unresolved_scope",),
        "metadata": {},
    }


def test_stage_payload_pads_typed_carrier() -> None:
    payload = persistence.StagePayload(
        "factor", texts=("factor:1",), ints=(7,), byteas=(b"x",)
    )
    row = payload.copy_row(
        stage_ref="stage:1",
        document_ref="document:1",
        build_key_sha256="abc",
        lane_ref="graph",
        partition_no=0,
        ordinal=4,
    )
    assert len(row) == 27
    assert row[:8] == (
        "stage:1",
        "document:1",
        "abc",
        "graph",
        "factor",
        0,
        4,
        "factor:1",
    )
    assert row[19] == 7
    assert row[25] == b"x"


def test_stage_payload_rejects_unbounded_fields() -> None:
    with pytest.raises(ValueError, match="twelve text"):
        persistence.StagePayload("row", texts=tuple("x" for _ in range(13)))


def test_deferred_factor_revision_has_no_database_side_effect() -> None:
    class RejectCursor:
        def execute(self, *_args: object, **_kwargs: object) -> None:
            raise AssertionError("deferred identity must not execute SQL")

    factor = _factor()
    observed = persistence.deferred_factor_revision(
        RejectCursor(), document_ref="document:1", factor=factor
    )
    assert observed == factor_revision_ref(factor)


def test_factor_payloads_preserve_revision_children() -> None:
    payloads, revisions = persistence._factor_payloads(
        document_ref="document:1",
        factors=(_factor(),),
        graph_ref="graph:1",
    )
    kinds = [row.row_kind_ref for row in payloads]
    assert revisions["factor:1"].startswith("factor-revision:")
    assert kinds == [
        "factor",
        "factor_revision",
        "graph_factor",
        "alternative",
        "factor_alternative",
        "residual",
    ]


def test_resolution_payloads_include_resulting_factor_children() -> None:
    prior = _factor(factor_ref="factor:prior")
    resulting = _factor(factor_ref="factor:prior")
    resulting["closure_state"] = "closed"
    refinement = {
        "refinement_ref": "refinement:1",
        "prior_factor": prior,
        "resulting_factor": resulting,
        "added_alternative_refs": (),
        "retained_alternative_refs": (),
        "rejected_alternative_refs": (),
        "residual_transitions": (),
    }
    with persistence.document_persistence_runtime(
        document_ref="document:1", build_key_sha256="build:1"
    ):
        payloads = persistence._resolution_payloads(
            factor_revisions={"factor:prior": factor_revision_ref(resulting)},
            demands=(),
            evidence=(),
            meets=(),
            refinements=(refinement,),
        )
    kinds = {row.row_kind_ref for row in payloads}
    assert {
        "factor",
        "factor_revision",
        "alternative",
        "factor_alternative",
        "residual",
        "refinement",
    } <= kinds


def test_binding_payloads_fail_closed_on_missing_revision() -> None:
    with pytest.raises(ValueError, match="unpersisted factor revision"):
        persistence._binding_payloads(
            candidate_sets=(),
            refinements=(),
            factor_revisions={},
            factor_anchors=(
                {
                    "factor_ref": "factor:missing",
                    "document_ref": "document:1",
                    "start_token": 0,
                    "end_token": 1,
                    "pnf_kind_ref": "predicate",
                },
            ),
            builds=(),
            meets=(),
            demands=(),
        )


def test_runtime_claims_and_returns_budget_once() -> None:
    events: list[str] = []
    with persistence.configure_work_conserving_persistence(
        worker_budget=8,
        before_persistence=lambda: events.append("claim"),
        after_persistence=lambda: events.append("return"),
    ):
        with persistence.document_persistence_runtime(
            document_ref="document:1", build_key_sha256="build:1"
        ) as runtime:
            runtime.ensure_budget()
            runtime.ensure_budget()
            assert runtime.worker_budget == 8
    assert events == ["claim", "return"]


def test_store_bindings_restore_instance_surface() -> None:
    class Store:
        def persist_token_batches(self, *_args: object, **_kwargs: object) -> str:
            return "original"

        def persist_annotation_layer(self, *_args: object, **_kwargs: object) -> None:
            return None

        def persist_annotation_layer_batches(
            self, *_args: object, **_kwargs: object
        ) -> None:
            return None

    store = Store()
    original = store.persist_token_batches
    with persistence.activate_work_conserving_store_bindings(store):
        assert store.persist_token_batches.__func__ is (
            persistence.persist_token_batches_work_conserving
        )
    assert store.persist_token_batches.__func__ is original.__func__


def test_compiler_bindings_restore_module_globals() -> None:
    import src.policy.postgres_corpus_compilation as compiler
    from src.storage.postgres import work_conserving_stage

    original_graph = compiler.persist_pnf_graph
    original_partition = work_conserving_stage._stage_partition
    with persistence.activate_work_conserving_postgres_bindings():
        assert compiler.persist_pnf_graph is (
            persistence.persist_pnf_graph_work_conserving
        )
        assert compiler.persist_licensed_spans is (
            persistence.persist_licensed_spans_work_conserving
        )
        assert work_conserving_stage._stage_partition is not original_partition
    assert compiler.persist_pnf_graph is original_graph
    assert work_conserving_stage._stage_partition is original_partition


def test_migration_is_typed_and_execution_only() -> None:
    root = Path(__file__).resolve().parents[2]
    sql = (
        root
        / "database/postgres_migrations/061_work_conserving_document_persistence.sql"
    ).read_text(encoding="utf-8")
    lowered = sql.casefold()
    assert "create unlogged table" in lowered
    assert "json" not in lowered
    assert "document_persistence_stage" in lowered
    assert "document_persistence_lane" in lowered
    assert "never semantic authority" in lowered


def test_work_conserving_authority_surface_has_no_json_serde() -> None:
    root = Path(__file__).resolve().parents[2]
    paths = (
        root / "src/storage/postgres/work_conserving_stage.py",
        root / "src/storage/postgres/work_conserving_copy_observability.py",
        root / "src/storage/postgres/work_conserving_graph_persistence.py",
        root / "src/storage/postgres/work_conserving_language_persistence.py",
        root / "src/storage/postgres/work_conserving_resolution_persistence.py",
        root / "src/storage/postgres/work_conserving_binding_persistence.py",
        root / "src/storage/postgres/work_conserving_persistence.py",
    )
    for path in paths:
        lowered = path.read_text(encoding="utf-8").casefold()
        assert "import json" not in lowered, path
        assert "json.dumps" not in lowered, path
        assert "json.loads" not in lowered, path
        assert "jsonb" not in lowered, path


def test_stage_partition_count_is_bounded_by_worker_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    submitted: list[int] = []

    class FakeConnection:
        def __enter__(self) -> "FakeConnection":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def cursor(self) -> "FakeConnection":
            return self

        def execute(self, *_args: object, **_kwargs: object) -> None:
            return None

    class FakePsycopg:
        @staticmethod
        def connect(_dsn: str) -> FakeConnection:
            return FakeConnection()

    class ImmediateFuture:
        def __init__(self, value: dict[str, int]) -> None:
            self._value = value

        def result(self) -> dict[str, int]:
            return self._value

    class ImmediateExecutor:
        def __init__(self, *, max_workers: int, **_kwargs: object) -> None:
            submitted.append(max_workers)

        def __enter__(self) -> "ImmediateExecutor":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def submit(self, _fn: object, **kwargs: object) -> ImmediateFuture:
            return ImmediateFuture({"partition_no": int(kwargs["partition_no"])})

    monkeypatch.setattr(stage, "_require_psycopg", lambda: FakePsycopg)
    monkeypatch.setattr(stage, "ThreadPoolExecutor", ImmediateExecutor)
    monkeypatch.setattr(stage, "as_completed", lambda futures: tuple(futures))
    stage._prepare_stage(
        dsn="postgresql://example",
        stage_ref="stage:1",
        document_ref="document:1",
        build_key_sha256="build:1",
        family_ref="test",
        lane_ref="graph",
        payloads=tuple(
            persistence.StagePayload("factor", texts=(str(index),))
            for index in range(10)
        ),
        worker_budget=4,
    )
    assert submitted == [4]
