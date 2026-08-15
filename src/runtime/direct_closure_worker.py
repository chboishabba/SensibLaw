"""Pure process worker for one semantic closure job.

This module deliberately lives below :mod:`src.policy` so spawned children do
not need to import the policy installation stack merely to execute one immutable
solver job.  The canonical :class:`PythonClosureExecutor` remains responsible
for proposal ordering and receipt construction; this worker only moves that
existing pure computation into the process that actually performs it.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


_EXECUTOR: Any | None = None


def _persist_receipt(path_raw: str, receipt: Any) -> None:
    path = Path(path_raw)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(receipt.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def execute_operator_solver_receipt(
    job: Any,
    receipt_path: str | None = None,
) -> Any:
    """Return and optionally durably checkpoint the canonical ``SolverReceipt``."""

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
    receipt = _EXECUTOR.execute(job)
    if receipt_path:
        _persist_receipt(receipt_path, receipt)
    return receipt


__all__ = ["execute_operator_solver_receipt"]
