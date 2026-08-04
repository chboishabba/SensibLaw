"""Install proactive stage budgets on the existing semantic telemetry seam."""

from __future__ import annotations

from typing import Any, Mapping

from src.runtime.stage_memory_budget import StageMemoryBudgetGuard


_INSTALL_MARKER = "_stage_budget_execution_installed"


def install_stage_budget_execution() -> bool:
    """Turn every semantic kernel sample into a durable budget observation.

    Semantic samples are required to resolve to an explicit stage family. A new
    kernel label therefore cannot silently degrade to ``unbudgeted`` telemetry
    during an exact-document run.
    """

    from src.policy import parallel_semantic_execution as semantic

    if getattr(semantic, _INSTALL_MARKER, False):
        return False
    original = semantic.SemanticExecutionContext.sample

    def sample_wrapper(
        self: Any,
        stage: str,
        *,
        phase: str,
        counts: Mapping[str, int] | None = None,
        details: Mapping[str, Any] | None = None,
        elapsed_ns: int | None = None,
    ) -> dict[str, Any]:
        guard = getattr(self, "_stage_memory_budget_guard", None)
        if guard is None:
            guard = StageMemoryBudgetGuard(root=self.checkpoint_root)
            setattr(self, "_stage_memory_budget_guard", guard)
        budget_receipt = guard.checkpoint(
            stage,
            phase=phase,
            semantic_counts=counts,
            details={
                **dict(details or {}),
                **({"kernel_elapsed_ns": elapsed_ns} if elapsed_ns is not None else {}),
            },
            require_budget=True,
        )
        row = original(
            self,
            stage,
            phase=phase,
            counts=counts,
            details={
                **dict(details or {}),
                "stage_budget_state": budget_receipt["state"],
                "stage_budget_family": budget_receipt["stage_family"],
                "stage_budget_headroom_bytes": budget_receipt.get("headroom_bytes"),
            },
            elapsed_ns=elapsed_ns,
        )
        row["stage_budget"] = budget_receipt
        return row

    semantic.SemanticExecutionContext.sample = sample_wrapper
    semantic._unbudgeted_semantic_sample = original
    setattr(semantic, _INSTALL_MARKER, True)
    return True


__all__ = ["install_stage_budget_execution"]
