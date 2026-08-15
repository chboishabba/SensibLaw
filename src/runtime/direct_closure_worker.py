"""Pure process worker for one semantic closure job.

This module deliberately lives below :mod:`src.policy` so spawned children do
not need to import the policy installation stack merely to execute one immutable
solver job.  The canonical :class:`PythonClosureExecutor` remains responsible
for proposal ordering and receipt construction; this worker only moves that
existing pure computation into the process that actually performs it.
"""

from __future__ import annotations

from typing import Any


_EXECUTOR: Any | None = None


def execute_operator_solver_receipt(job: Any) -> Any:
    """Return the canonical ``SolverReceipt`` for one immutable operator job."""

    global _EXECUTOR
    if _EXECUTOR is None:
        from src.pnf.streaming_fixed_point import PythonClosureExecutor
        from src.pnf.streaming_operator_executor import (
            STREAMING_OPERATOR_DECLARATION_REF,
            solve_operator_job,
        )

        _EXECUTOR = PythonClosureExecutor(
            {STREAMING_OPERATOR_DECLARATION_REF: solve_operator_job}
        )
    return _EXECUTOR.execute(job)


__all__ = ["execute_operator_solver_receipt"]
