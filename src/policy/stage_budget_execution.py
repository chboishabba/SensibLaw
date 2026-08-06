"""Install proactive stage budgets on the semantic telemetry seam."""

from __future__ import annotations

from typing import Any, Mapping

from src.runtime.stage_memory_budget import StageMemoryBudgetGuard


_INSTALL_MARKER = "_stage_budget_execution_installed"


def install_stage_budget_execution() -> bool:
    """Install typed durability and enforce every semantic budget sample."""

    from src.policy import parallel_semantic_execution as semantic
    from src.policy.durable_work_item_execution import (
        install_durable_work_item_execution,
    )
    from src.policy.no_json_checkpoint_execution import (
        install_no_json_checkpoint_execution,
    )
    from src.policy.typed_execution_callback_views import (
        install_typed_execution_callback_views,
    )
    from src.storage.postgres.typed_execution_pool import (
        install_typed_execution_pool,
    )

    if getattr(semantic, _INSTALL_MARKER, False):
        return False
    # These policies wrap physical execution only. Binary format enforcement,
    # append-only admission, and typed callback views must precede replay.
    install_no_json_checkpoint_execution()
    install_typed_execution_pool()
    install_typed_execution_callback_views()
    install_durable_work_item_execution()
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
        )
        row = original(
            self,
            stage,
            phase=phase,
            counts=counts,
            details={
                **dict(details or {}),
                "stage_budget_state": budget_receipt["state"],
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
