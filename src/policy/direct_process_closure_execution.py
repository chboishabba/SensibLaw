"""Direct process-backed execution for the bounded closure scheduler.

The bounded scheduler already owns leasing, backpressure and serial owner
admission.  The earlier multicore bridge ran each leased job through a thread,
which submitted the same immutable job to the shared semantic process pool and
blocked on ``Future.result()``.  That added a second scheduler and one extra
cross-thread handoff per sentence.

This execution-only adapter lets the bounded scheduler submit directly to the
already-managed process pool.  Child processes still execute the canonical
``PythonClosureExecutor`` and return the same ``SolverReceipt``.  If process
execution is disabled (worker width 1), or receipt-stop fault injection is
active, the original thread executor is used unchanged.
"""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor as _ThreadPoolExecutor
import os
from typing import Any

from src.runtime.direct_closure_worker import execute_operator_solver_receipt


_INSTALL_MARKER = "_direct_process_closure_execution_installed"


def _receipt_stop_injection_active() -> bool:
    raw = os.environ.get("SENSIBLAW_CLOSURE_STOP_AFTER_RECEIPTS", "0")
    try:
        return int(raw or "0") > 0
    except ValueError:
        return False


class DirectProcessClosurePool:
    """Executor facade preserving the bounded scheduler's ``submit`` contract."""

    def __init__(
        self,
        *,
        max_workers: int,
        thread_name_prefix: str = "",
        **_kwargs: Any,
    ) -> None:
        from src.policy.durable_work_item_execution import _durable_pool

        self._process_pool = (
            None if _receipt_stop_injection_active() else _durable_pool()
        )
        self._thread_pool = (
            None
            if self._process_pool is not None
            else _ThreadPoolExecutor(
                max_workers=max_workers,
                thread_name_prefix=thread_name_prefix,
            )
        )

    @property
    def process_backed(self) -> bool:
        return self._process_pool is not None

    def submit(self, function: Any, job: Any):
        if self._process_pool is not None:
            from src.policy import parallel_semantic_execution as parallel

            context = parallel._context_for_document(job.owner_key.document_ref)
            receipt_path = (
                context.closure_receipt_path(job.job_ref)
                if context is not None
                else None
            )
            if receipt_path is not None and receipt_path.exists():
                payload = parallel._read_json(receipt_path)
                if payload is not None:
                    receipt = parallel._solver_receipt_from_row(payload)
                    if context is not None:
                        with context.lock:
                            context.closure_counters["receipts_reused"] += 1
                    completed: Future[Any] = Future()
                    completed.set_result(receipt)
                    return completed

            # The scheduler's function is the canonical closure executor bound
            # in the parent. Recreate that pure executor inside the child so we
            # transfer only the immutable SolverJob and canonical SolverReceipt,
            # not a closure containing parent execution policy. Persist the
            # receipt before resolving the future, preserving crash-before-owner-
            # admission reuse from the former parent execute wrapper.
            future = self._process_pool.submit(
                execute_operator_solver_receipt,
                job,
                str(receipt_path) if receipt_path is not None else None,
            )
            if context is not None:
                def record_completion(done: Future[Any]) -> None:
                    try:
                        receipt = done.result()
                    except BaseException:
                        return
                    with context.lock:
                        context.closure_counters["receipts_computed"] += 1
                        context.closure_counters["proposals_emitted"] += len(
                            receipt.proposals
                        )
                        context.closure_counters["dependency_fanout"] += sum(
                            len(proposal.dependency_factor_refs)
                            for proposal in receipt.proposals
                        )

                future.add_done_callback(record_completion)
            return future

        assert self._thread_pool is not None
        return self._thread_pool.submit(function, job)

    def shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None:
        # The process pool is shared with bounded typing leaves and is released by
        # the existing document compile finalizer. Shutting it down here would
        # make each bounded closure block pay process startup/teardown again.
        if self._thread_pool is not None:
            self._thread_pool.shutdown(
                wait=wait,
                cancel_futures=cancel_futures,
            )

    def __enter__(self) -> "DirectProcessClosurePool":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.shutdown(wait=True, cancel_futures=exc_type is not None)


def install_direct_process_closure_execution() -> bool:
    """Route the bounded closure scheduler straight to process workers."""

    from src.policy import bounded_operational_execution as bounded
    from src.policy.activation_hot_path_execution import (
        install_activation_hot_path_execution,
    )

    if getattr(bounded, _INSTALL_MARKER, False):
        return False
    bounded.ThreadPoolExecutor = DirectProcessClosurePool
    # Activation descriptors are checkpoint metadata over immutable deltas, not
    # semantic computation. Keep those in the coordinator so this process pool
    # is reserved for work whose CPU cost actually benefits from multiprocessing.
    install_activation_hot_path_execution()
    setattr(bounded, _INSTALL_MARKER, True)
    return True


__all__ = [
    "DirectProcessClosurePool",
    "install_direct_process_closure_execution",
]
