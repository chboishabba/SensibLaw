"""Direct process-backed execution for the bounded closure scheduler.

The bounded scheduler already owns leasing, backpressure and serial owner
admission.  The earlier multicore bridge ran each leased job through a thread,
which submitted the same immutable job to the shared semantic process pool and
blocked on ``Future.result()``.  That added a second scheduler and one extra
cross-thread handoff per sentence.

This execution-only adapter lets the bounded scheduler submit directly to the
already-managed process pool.  Child processes still execute the canonical
``PythonClosureExecutor`` and return the same ``SolverReceipt``.  If process
execution is disabled (worker width 1), the original thread executor is used
unchanged.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor as _ThreadPoolExecutor
from typing import Any

from src.runtime.direct_closure_worker import execute_operator_solver_receipt


_INSTALL_MARKER = "_direct_process_closure_execution_installed"


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

        self._process_pool = _durable_pool()
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
            # The scheduler's function is the canonical closure executor bound
            # in the parent.  Recreate that pure executor inside the child so we
            # transfer only the immutable SolverJob and canonical SolverReceipt,
            # not a closure containing parent execution policy.
            return self._process_pool.submit(execute_operator_solver_receipt, job)
        assert self._thread_pool is not None
        return self._thread_pool.submit(function, job)

    def shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None:
        # The process pool is shared with bounded typing leaves and is released by
        # the existing document compile finalizer.  Shutting it down here would
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
