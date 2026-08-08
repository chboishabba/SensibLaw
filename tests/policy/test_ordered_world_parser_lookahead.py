from __future__ import annotations

from concurrent.futures import Future
import json

import pytest

from src.pnf.document_fibres import DocumentFibrePolicy
from src.policy.ordered_world_parser_lookahead import (
    ORDERED_WORLD_LOOKAHEAD_CONTRACT,
    OrderedWorldParserLookahead,
    ParserLookaheadAllocation,
    ParserPrefetchCandidate,
    allocate_parser_lookahead,
    compile_directory_postgres_ordered_world,
)
from src.policy.ordered_world_parser_lookahead import _completed_document_refs


def test_parser_lookahead_reserves_matching_parser_lane() -> None:
    allocation = allocate_parser_lookahead(
        global_worker_budget=4,
        parser_workers=2,
    )

    assert allocation.enabled is True
    assert allocation.parser_lookahead_workers == 2
    assert allocation.foreground_worker_budget == 2
    assert (
        allocation.foreground_worker_budget
        + allocation.parser_lookahead_workers
        == allocation.global_worker_budget
    )


def test_parser_lookahead_disables_when_identity_preserving_split_is_impossible() -> None:
    allocation = allocate_parser_lookahead(
        global_worker_budget=3,
        parser_workers=2,
    )

    assert allocation.enabled is False
    assert allocation.parser_lookahead_workers == 0
    assert allocation.foreground_worker_budget == 3
    assert "required=4" in allocation.reason


def test_allocation_rejects_global_oversubscription() -> None:
    with pytest.raises(ValueError, match="exceed the global worker budget"):
        ParserLookaheadAllocation(
            global_worker_budget=4,
            foreground_worker_budget=3,
            parser_lookahead_workers=2,
            enabled=True,
            reason="invalid",
        )


def test_completed_document_refs_admit_only_published_states(tmp_path) -> None:
    state_path = tmp_path / "compile.json"
    state_path.write_text(
        json.dumps(
            {
                "documents": {
                    "document:1": {"state": "compiled"},
                    "document:2": {"state": "reused_compilation"},
                    "document:3": {"state": "running"},
                    "document:4": {"state": "failed"},
                }
            }
        ),
        encoding="utf-8",
    )

    assert _completed_document_refs(state_path) == {"document:1", "document:2"}


def test_ordered_world_rejects_parallel_semantic_documents() -> None:
    with pytest.raises(ValueError, match="document_workers=1"):
        compile_directory_postgres_ordered_world(
            ".",
            document_workers=2,
        )


def test_disabled_lookahead_forwards_to_ordered_compiler(monkeypatch) -> None:
    import src.policy.postgres_corpus_compilation as postgres_compilation

    calls: list[tuple[str, dict[str, object]]] = []

    def fake_compile(input_dir: str, **kwargs: object) -> str:
        calls.append((input_dir, kwargs))
        return "compiled"

    monkeypatch.setenv("SENSIBLAW_ORDERED_WORLD_LOOKAHEAD", "0")
    monkeypatch.setattr(
        postgres_compilation,
        "compile_directory_postgres",
        fake_compile,
    )

    result = compile_directory_postgres_ordered_world(
        "corpus",
        document_workers=1,
        worker_budget=4,
    )

    assert result == "compiled"
    assert calls == [
        (
            "corpus",
            {
                "document_workers": 1,
                "worker_budget": 4,
            },
        )
    ]


def _candidate(tmp_path) -> ParserPrefetchCandidate:
    return ParserPrefetchCandidate(
        sequence_no=8,
        document_ref="document:0008",
        relative_path="0008.txt",
        source_path="0008.txt",
        media_type="text/plain",
        source_ref="document-source:0008",
        checkpoint_dir=str(tmp_path / "chunks"),
        canonical_chars=2_000_000,
    )


def _coordinator(tmp_path, candidate) -> OrderedWorldParserLookahead:
    return OrderedWorldParserLookahead(
        candidates=(candidate,),
        parser_policy=DocumentFibrePolicy(workers=1),
        receipt_path=tmp_path / "lookahead.json",
        allocation=ParserLookaheadAllocation(
            global_worker_budget=2,
            foreground_worker_budget=1,
            parser_lookahead_workers=1,
            enabled=True,
            reason="test",
        ),
    )


def test_prefetch_failure_falls_back_to_foreground(tmp_path) -> None:
    candidate = _candidate(tmp_path)
    coordinator = _coordinator(tmp_path, candidate)
    future: Future[dict[str, object]] = Future()
    future.set_exception(RuntimeError("prefetch failed"))
    coordinator._active_candidate = candidate
    coordinator._active_future = future  # type: ignore[assignment]

    result = coordinator.wait_for(candidate.document_ref)

    assert result is not None
    assert result["state"] == "prefetch_failed_fallback_to_foreground"
    assert coordinator._active_future is None
    assert coordinator._active_candidate is None


def test_cleanup_does_not_replace_foreground_failure(tmp_path) -> None:
    class FakeExecutor:
        def __init__(self) -> None:
            self.shutdown_calls: list[tuple[bool, bool]] = []

        def shutdown(self, *, wait: bool, cancel_futures: bool) -> None:
            self.shutdown_calls.append((wait, cancel_futures))

    candidate = _candidate(tmp_path)
    coordinator = _coordinator(tmp_path, candidate)
    future: Future[dict[str, object]] = Future()
    future.set_exception(RuntimeError("prefetch failed"))
    executor = FakeExecutor()
    coordinator._executor = executor  # type: ignore[assignment]
    coordinator._active_candidate = candidate
    coordinator._active_future = future  # type: ignore[assignment]

    coordinator.close(propagate_errors=False)

    payload = json.loads((tmp_path / "lookahead.json").read_text(encoding="utf-8"))
    assert payload["state"] == "foreground_failed"
    assert executor.shutdown_calls == [(False, True)]


def test_cleanup_propagates_prefetch_failure_without_foreground_failure(
    tmp_path,
) -> None:
    class FakeExecutor:
        def shutdown(self, *, wait: bool, cancel_futures: bool) -> None:
            assert wait is True
            assert cancel_futures is True

    candidate = _candidate(tmp_path)
    coordinator = _coordinator(tmp_path, candidate)
    future: Future[dict[str, object]] = Future()
    future.set_exception(RuntimeError("prefetch failed"))
    coordinator._executor = FakeExecutor()  # type: ignore[assignment]
    coordinator._active_candidate = candidate
    coordinator._active_future = future  # type: ignore[assignment]

    with pytest.raises(RuntimeError, match="prefetch failed"):
        coordinator.close(propagate_errors=True)


def test_contract_names_parser_authority_only() -> None:
    assert ORDERED_WORLD_LOOKAHEAD_CONTRACT == "ordered-world-parser-lookahead:v0_1"
