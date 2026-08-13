"""Ordered world compilation with work-conserving parser/persistence ownership."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from src.pnf.document_fibres import DocumentFibrePolicy
from src.policy.ordered_world_parser_lookahead import (
    ORDERED_WORLD_LOOKAHEAD_CONTRACT,
    OrderedWorldParserLookahead,
    ParserLookaheadAllocation,
    ParserPrefetchCandidate,
    _cooperative_parser_replay,
    _lookahead_candidates,
    allocate_parser_lookahead,
)
from src.policy.work_conserving_postgres_corpus_compilation import (
    WORK_CONSERVING_DOCUMENT_EXECUTOR_REF,
    WORK_CONSERVING_PERSISTENCE_CONTRACT,
    persist_document_compilation_work_conserving,
)
from src.storage.postgres.work_conserving_persistence import (
    configure_work_conserving_persistence,
)


WORK_CONSERVING_ORDERED_CONTRACT = "ordered-world-work-conserving:v0_1"


class WorkConservingOrderedWorldParserLookahead(OrderedWorldParserLookahead):
    """Transfer the entire application budget to the active foreground kernel."""

    def __init__(
        self,
        *,
        candidates: tuple[ParserPrefetchCandidate, ...],
        parser_policy: DocumentFibrePolicy,
        receipt_path: Path,
        allocation: ParserLookaheadAllocation,
    ) -> None:
        super().__init__(
            candidates=candidates,
            parser_policy=parser_policy,
            receipt_path=receipt_path,
            allocation=allocation,
        )
        self._foreground_kernel_owns_budget = False
        self._completed_unconsumed: dict[str, Any] | None = None

    def _schedule_next(self) -> None:
        if self._foreground_kernel_owns_budget:
            self._state = "foreground_kernel_owns_budget"
            self._write_receipt()
            return
        if self._completed_unconsumed is not None:
            self._state = "completed_parser_buffer_waiting_for_foreground"
            self._write_receipt()
            return
        super()._schedule_next()

    def wait_for(self, document_ref: str) -> dict[str, Any] | None:
        buffered = self._completed_unconsumed
        if buffered is not None and str(buffered.get("document_ref")) == document_ref:
            self._completed_unconsumed = None
            if not self._foreground_kernel_owns_budget:
                self._state = "running"
                self._schedule_next()
            else:
                self._write_receipt()
            return buffered
        return super().wait_for(document_ref)

    def quiesce_for_foreground_kernel(self) -> None:
        """Finish one speculative parse, then return all workers to persistence."""

        if self._foreground_kernel_owns_budget:
            return
        self._foreground_kernel_owns_budget = True
        candidate = self._active_candidate
        future = self._active_future
        if candidate is not None and future is not None:
            try:
                result = future.result()
            except BaseException as error:
                result = {
                    "document_ref": candidate.document_ref,
                    "relative_path": candidate.relative_path,
                    "checkpoint_dir": candidate.checkpoint_dir,
                    "state": "prefetch_failed_fallback_to_foreground",
                    "error_type": type(error).__name__,
                    "error": str(error),
                    "authority": "parser_observation_only",
                }
            else:
                result = {
                    **result,
                    "state": "completed_before_persistence_budget_transfer",
                }
            self._results.append(result)
            self._completed_unconsumed = result
            self._active_candidate = None
            self._active_future = None
        self._state = "foreground_kernel_owns_budget"
        self._write_receipt()

    def resume_parser_lookahead(self) -> None:
        if not self._foreground_kernel_owns_budget:
            return
        self._foreground_kernel_owns_budget = False
        if self._executor is not None:
            if self._completed_unconsumed is None:
                self._state = "running"
                self._schedule_next()
            else:
                self._state = "completed_parser_buffer_waiting_for_foreground"
                self._write_receipt()
        else:
            self._write_receipt()


def compile_directory_postgres_work_conserving_ordered(
    input_dir: str | Path,
    **compile_kwargs: Any,
) -> Any:
    """Compile one ordered semantic document while saturating its hot kernel."""

    document_workers = int(compile_kwargs.get("document_workers", 1))
    if document_workers != 1:
        raise ValueError(
            "ordered world compilation requires document_workers=1; "
            "parallelism belongs below the single semantic frontier"
        )

    from src.policy.postgres_corpus_compilation import compile_directory_postgres

    state_value = compile_kwargs.get("state_path")
    state_path = Path(state_value).resolve() if state_value is not None else None
    parser_workers = int(compile_kwargs.get("parser_workers", 2))
    worker_budget = int(
        compile_kwargs.get("worker_budget")
        if compile_kwargs.get("worker_budget") is not None
        else max(1, parser_workers)
    )
    lookahead_enabled = (
        state_path is not None
        and os.environ.get("SENSIBLAW_ORDERED_WORLD_LOOKAHEAD", "1") != "0"
    )
    allocation = allocate_parser_lookahead(
        global_worker_budget=worker_budget,
        parser_workers=parser_workers,
    )
    parser_policy = DocumentFibrePolicy(
        workers=parser_workers,
        parser_limit_chars=int(compile_kwargs.get("parser_limit_chars", 1_000_000)),
        target_chars=int(compile_kwargs.get("parser_target_chars", 400_000)),
        overlap_chars=int(compile_kwargs.get("parser_overlap_chars", 8_192)),
    )
    candidates: tuple[ParserPrefetchCandidate, ...] = ()
    if lookahead_enabled and allocation.enabled and state_path is not None:
        candidates = _lookahead_candidates(
            input_dir,
            context=compile_kwargs["context"],
            state_path=state_path,
            parser_policy=parser_policy,
            recursive=bool(compile_kwargs.get("recursive", True)),
            follow_symlinks=bool(compile_kwargs.get("follow_symlinks", False)),
            include_globs=tuple(compile_kwargs.get("include_globs") or ()),
            exclude_globs=tuple(compile_kwargs.get("exclude_globs") or ()),
            max_files=compile_kwargs.get("max_files"),
            max_file_bytes=compile_kwargs.get("max_file_bytes"),
            max_total_bytes=compile_kwargs.get("max_total_bytes"),
            admission_policy=compile_kwargs.get("admission_policy"),
        )
    receipt_path = (
        state_path.with_name(f"{state_path.stem}_parser_lookahead.json")
        if state_path is not None
        else Path(".tmp/work-conserving-parser-lookahead.json").resolve()
    )
    coordinator = WorkConservingOrderedWorldParserLookahead(
        candidates=candidates,
        parser_policy=parser_policy,
        receipt_path=receipt_path,
        allocation=(
            allocation
            if lookahead_enabled
            else ParserLookaheadAllocation(
                global_worker_budget=worker_budget,
                foreground_worker_budget=worker_budget,
                parser_lookahead_workers=0,
                enabled=False,
                reason="lookahead_disabled",
            )
        ),
    )
    resource_ledger = compile_kwargs.get("resource_ledger")
    if resource_ledger is not None:
        resource_ledger.sample(
            "work_conserving_ordered:start",
            phase="postgres_persistence",
            semantic_counts={"candidate_documents": len(candidates)},
            details={
                "contract_ref": WORK_CONSERVING_ORDERED_CONTRACT,
                "lookahead_contract_ref": ORDERED_WORLD_LOOKAHEAD_CONTRACT,
                "persistence_contract_ref": WORK_CONSERVING_PERSISTENCE_CONTRACT,
                "global_worker_budget": worker_budget,
            },
        )
    coordinator.start()
    foreground_kwargs = dict(compile_kwargs)
    foreground_kwargs.update(
        document_executor=persist_document_compilation_work_conserving,
        document_executor_ref=WORK_CONSERVING_DOCUMENT_EXECUTOR_REF,
        persistence_strategy_ref=WORK_CONSERVING_PERSISTENCE_CONTRACT,
    )
    if allocation.enabled and candidates:
        foreground_kwargs["worker_budget"] = allocation.foreground_worker_budget

    foreground_error: BaseException | None = None
    try:
        with configure_work_conserving_persistence(
            worker_budget=worker_budget,
            before_persistence=coordinator.quiesce_for_foreground_kernel,
            after_persistence=coordinator.resume_parser_lookahead,
        ):
            with _cooperative_parser_replay(coordinator):
                return compile_directory_postgres(input_dir, **foreground_kwargs)
    except BaseException as error:
        foreground_error = error
        raise
    finally:
        coordinator.close(propagate_errors=False)
        if resource_ledger is not None:
            resource_ledger.sample(
                "work_conserving_ordered:after",
                phase="postgres_persistence",
                semantic_counts={"candidate_documents": len(candidates)},
                details={
                    "contract_ref": WORK_CONSERVING_ORDERED_CONTRACT,
                    "receipt_ref": str(receipt_path),
                    "foreground_state": (
                        "failed" if foreground_error is not None else "completed"
                    ),
                },
            )


__all__ = [
    "WORK_CONSERVING_ORDERED_CONTRACT",
    "WorkConservingOrderedWorldParserLookahead",
    "compile_directory_postgres_work_conserving_ordered",
]
