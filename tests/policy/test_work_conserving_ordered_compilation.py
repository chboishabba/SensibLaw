from __future__ import annotations

from concurrent.futures import Future
from pathlib import Path

import pytest

from src.pnf.document_fibres import DocumentFibrePolicy
from src.policy.ordered_world_parser_lookahead import (
    ParserLookaheadAllocation,
    ParserPrefetchCandidate,
)
from src.policy.work_conserving_ordered_compilation import (
    WorkConservingOrderedWorldParserLookahead,
    compile_directory_postgres_work_conserving_ordered,
)
from src.policy.work_conserving_postgres_corpus_compilation import (
    WORK_CONSERVING_DOCUMENT_EXECUTOR_REF,
    persist_document_compilation_work_conserving,
)
from src.storage.postgres.work_conserving_persistence import (
    WORK_CONSERVING_PERSISTENCE_CONTRACT,
)


def _candidate(tmp_path: Path) -> ParserPrefetchCandidate:
    return ParserPrefetchCandidate(
        sequence_no=7,
        document_ref="document:7",
        relative_path="0007.txt",
        source_path=str(tmp_path / "0007.txt"),
        media_type="text/plain",
        source_ref="document-source:7",
        checkpoint_dir=str(tmp_path / "chunks"),
        canonical_chars=700_000,
    )


def _coordinator(tmp_path: Path) -> WorkConservingOrderedWorldParserLookahead:
    return WorkConservingOrderedWorldParserLookahead(
        candidates=(_candidate(tmp_path),),
        parser_policy=DocumentFibrePolicy(workers=2),
        receipt_path=tmp_path / "receipt.json",
        allocation=ParserLookaheadAllocation(
            global_worker_budget=4,
            foreground_worker_budget=2,
            parser_lookahead_workers=2,
            enabled=True,
            reason="test",
        ),
    )


def test_persistence_budget_transfer_finishes_active_parser(tmp_path: Path) -> None:
    coordinator = _coordinator(tmp_path)
    future: Future[dict[str, object]] = Future()
    future.set_result(
        {
            "document_ref": "document:7",
            "elapsed_ms": 23,
            "authority": "parser_observation_only",
        }
    )
    coordinator._active_candidate = _candidate(tmp_path)
    coordinator._active_future = future

    coordinator.quiesce_for_foreground_kernel()

    assert coordinator._foreground_kernel_owns_budget is True
    assert coordinator._active_candidate is None
    assert coordinator._active_future is None
    assert coordinator._state == "foreground_kernel_owns_budget"
    assert coordinator._results[-1]["state"] == (
        "completed_before_persistence_budget_transfer"
    )


def test_persistence_budget_transfer_keeps_prefetch_non_authoritative(
    tmp_path: Path,
) -> None:
    coordinator = _coordinator(tmp_path)
    future: Future[dict[str, object]] = Future()
    future.set_exception(RuntimeError("parser failed"))
    coordinator._active_candidate = _candidate(tmp_path)
    coordinator._active_future = future

    coordinator.quiesce_for_foreground_kernel()

    assert coordinator._results[-1]["state"] == (
        "prefetch_failed_fallback_to_foreground"
    )
    assert coordinator._results[-1]["authority"] == "parser_observation_only"


def test_parser_resumes_only_after_budget_return(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    coordinator = _coordinator(tmp_path)
    coordinator._foreground_kernel_owns_budget = True
    coordinator._executor = object()  # type: ignore[assignment]
    scheduled: list[str] = []
    monkeypatch.setattr(
        coordinator, "_schedule_next", lambda: scheduled.append("scheduled")
    )

    coordinator.resume_parser_lookahead()

    assert coordinator._foreground_kernel_owns_budget is False
    assert scheduled == ["scheduled"]


def test_completed_parser_buffer_blocks_second_future_until_consumed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    coordinator = _coordinator(tmp_path)
    coordinator._foreground_kernel_owns_budget = True
    coordinator._executor = object()  # type: ignore[assignment]
    buffered = {
        "document_ref": "document:7",
        "authority": "parser_observation_only",
        "state": "completed_before_persistence_budget_transfer",
    }
    coordinator._completed_unconsumed = buffered
    scheduled: list[str] = []
    monkeypatch.setattr(
        coordinator,
        "_schedule_next",
        lambda: scheduled.append("scheduled"),
    )

    coordinator.resume_parser_lookahead()

    assert scheduled == []
    assert coordinator._state == ("completed_parser_buffer_waiting_for_foreground")
    assert coordinator.wait_for("document:7") is buffered
    assert scheduled == ["scheduled"]


def test_ordered_wrapper_rejects_parallel_semantic_documents() -> None:
    with pytest.raises(ValueError, match="document_workers=1"):
        compile_directory_postgres_work_conserving_ordered(".", document_workers=2)


def test_ordered_wrapper_injects_work_conserving_executor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import src.policy.postgres_corpus_compilation as compiler

    observed: dict[str, object] = {}

    def fake_compile(_input_dir: object, **kwargs: object) -> str:
        observed.update(kwargs)
        return "compiled"

    monkeypatch.setattr(compiler, "compile_directory_postgres", fake_compile)
    monkeypatch.setenv("SENSIBLAW_ORDERED_WORLD_LOOKAHEAD", "0")
    monkeypatch.chdir(tmp_path)

    result = compile_directory_postgres_work_conserving_ordered(
        tmp_path,
        context=object(),
        document_workers=1,
        parser_workers=2,
        worker_budget=4,
    )

    assert result == "compiled"
    assert observed["document_executor"] is (
        persist_document_compilation_work_conserving
    )
    assert observed["document_executor_ref"] == (WORK_CONSERVING_DOCUMENT_EXECUTOR_REF)
    assert observed["persistence_strategy_ref"] == (
        WORK_CONSERVING_PERSISTENCE_CONTRACT
    )
    assert observed["worker_budget"] == 4
