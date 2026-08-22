from __future__ import annotations

from contextlib import nullcontext

import pytest

from src.pnf.numeric_hyperfabric import WorkOperation
from src.storage.postgres import numeric_hyperfabric_store as store
from src.storage.postgres.numeric_hyperfabric_store import _load_sentence_tokens


class _Cursor:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self.rows = rows

    def execute(self, _query: str, _parameters: tuple[int, ...]) -> None:
        pass

    def fetchall(self) -> list[tuple[object, ...]]:
        return self.rows


def test_sentence_closure_rejects_missing_persisted_dependency_head() -> None:
    cursor = _Cursor(
        [
            (
                41,
                1,
                2,
                3,
                4,
                5,
                None,
                None,
                0,
                4,
            )
        ]
    )

    with pytest.raises(RuntimeError, match="missing.*numeric head"):
        _load_sentence_tokens(cursor, region_id=9)


class _DrainCursor:
    def __enter__(self) -> "_DrainCursor":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, *_args: object) -> None:
        return None


class _DrainConnection:
    def transaction(self):  # type: ignore[no-untyped-def]
        return nullcontext()

    def cursor(self) -> _DrainCursor:
        return _DrainCursor()

    def close(self) -> None:
        return None


def test_drain_sentence_closure_installs_setwise_admission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lease = store.WorkLease(
        work_id=1,
        region_id=2,
        operation=WorkOperation.SENTENCE_CLOSE,
        lease_token="lease",
        lease_epoch=3,
    )
    claims = iter((lease, None))
    observed: dict[str, object] = {}

    monkeypatch.setattr(store, "connect", lambda _database_url: _DrainConnection())
    monkeypatch.setattr(store, "claim_work", lambda *_args, **_kwargs: next(claims))
    monkeypatch.setattr(store, "_load_sentence_tokens", lambda *_args: ("tokens",))
    monkeypatch.setattr(store, "_load_profile", lambda *_args: "profile")
    monkeypatch.setattr(store, "_operator_lexicon", lambda *_args: "lexicon")
    monkeypatch.setattr(store, "compose_numeric_sentence", lambda **_kwargs: "closure")
    monkeypatch.setattr(
        store,
        "_persist_sentence_closure",
        lambda **_kwargs: pytest.fail("legacy row-wise admission was called"),
    )

    from src.storage.postgres import numeric_sentence_admission

    def persist_setwise(_cursor: object, **kwargs: object) -> int:
        observed.update(kwargs)
        return 4

    monkeypatch.setattr(
        numeric_sentence_admission,
        "persist_sentence_closure_setwise",
        persist_setwise,
    )

    assert (
        store.drain_sentence_closure(
            "postgresql://example", run_ref="run", worker_ref="worker"
        )
        == 1
    )
    assert observed["lease"] == lease
    assert observed["closure"] == "closure"
    assert observed["profile"] == "profile"
