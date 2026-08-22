"""Install proactive stage budgets on the semantic telemetry seam."""

from __future__ import annotations

from typing import Any, Mapping

from src.runtime.stage_memory_budget import StageMemoryBudgetGuard


_INSTALL_MARKER = "_stage_budget_execution_installed"


def install_stage_budget_execution() -> bool:
    """Install typed durability and require explicit semantic budget families."""

    from src.policy import parallel_semantic_execution as semantic
    from src.policy.binary_family_integrity_execution import (
        install_binary_family_integrity_execution,
    )
    from src.policy.durable_work_item_execution import (
        install_durable_work_item_execution,
    )
    from src.policy.no_json_checkpoint_execution import (
        install_no_json_checkpoint_execution,
    )
    from src.policy.numeric_head_integrity_execution import (
        install_numeric_head_integrity_execution,
    )
    from src.policy.numeric_kernel_timing_execution import (
        install_numeric_kernel_timing_execution,
    )
    from src.policy.numeric_semantic_receipt_execution import (
        install_numeric_semantic_receipt_execution,
    )
    from src.policy.streaming_spacy_parser_execution import (
        install_streaming_spacy_parser_execution,
    )
    from src.policy.typed_execution_callback_views import (
        install_typed_execution_callback_views,
    )
    from src.storage.postgres.deterministic_admission_execution import (
        install_deterministic_admission_execution,
    )
    from src.storage.postgres.typed_execution_pool import (
        install_typed_execution_pool,
    )

    if getattr(semantic, _INSTALL_MARKER, False):
        return False
    # These policies wrap physical execution only. Binary format enforcement,
    # streamed parser authority, explicit numeric head integrity, portable
    # numeric publication identity, kernel timing projection, pre-decode
    # integrity, concurrent typed staging, canonical admission, and callback
    # views precede first replay.
    install_no_json_checkpoint_execution()
    install_streaming_spacy_parser_execution()
    install_numeric_head_integrity_execution()
    install_numeric_semantic_receipt_execution()
    install_numeric_kernel_timing_execution()
    install_binary_family_integrity_execution()
    install_typed_execution_pool()
    install_deterministic_admission_execution()
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
