"""Install executable kernel contracts on the semantic execution boundary.

The semantic compiler remains pure and storage-neutral.  This layer wraps only
physical execution telemetry and the closure-handoff adapter, persisting a
finite diagnostic before rejecting an opaque wait, illegal lifecycle change,
post-drain admission, or silent authority fallback.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

from src.runtime.execution_kernel_contract import (
    KernelContractViolation,
    KernelRegistry,
)


_INSTALL_MARKER = "_execution_kernel_contracts_installed"


def _enabled() -> bool:
    value = os.environ.get("SENSIBLAW_ENFORCE_KERNEL_CONTRACTS", "1")
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _persist(context: Any, event: Mapping[str, Any]) -> None:
    root = getattr(context, "checkpoint_root", None)
    if root is None:
        return
    contract_root = Path(root) / "kernel-contracts"
    _atomic_json(contract_root / "latest.json", event)
    contract_root.mkdir(parents=True, exist_ok=True)
    with (contract_root / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(dict(event), ensure_ascii=False, sort_keys=True) + "\n")
        stream.flush()


def install_execution_kernel_contracts() -> bool:
    """Require registered bounded contracts for every semantic execution sample."""

    if not _enabled():
        return False

    from src.policy import parallel_semantic_execution as semantic

    if getattr(semantic, _INSTALL_MARKER, False):
        return False

    original_sample = semantic.SemanticExecutionContext.sample

    def sample_wrapper(
        self: Any,
        stage: str,
        *,
        phase: str,
        counts: Mapping[str, int] | None = None,
        details: Mapping[str, Any] | None = None,
        elapsed_ns: int | None = None,
    ) -> dict[str, Any]:
        registry = getattr(self, "_execution_kernel_registry", None)
        if registry is None:
            registry = KernelRegistry()
            setattr(self, "_execution_kernel_registry", registry)

        count_values = dict(counts or {})
        detail_values = dict(details or {})
        if stage in {"owner_admission_batch", "owner_frontier_reconstruction"}:
            count_values.setdefault(
                "new_durable_obligations",
                int(getattr(self, "_kernel_new_durable_obligations", 0)),
            )
            count_values.setdefault(
                "durable_admissions",
                int(getattr(self, "_kernel_durable_admissions", 0)),
            )
            detail_values.setdefault(
                "frontier_drained",
                bool(getattr(self, "_kernel_frontier_drained", False)),
            )
            detail_values.setdefault(
                "authority_backend",
                str(
                    getattr(
                        self,
                        "_kernel_authority_backend",
                        os.environ.get("SENSIBLAW_EXECUTION_AUTHORITY", "checkpoint"),
                    )
                ),
            )
            detail_values.setdefault(
                "authority_row_count",
                int(getattr(self, "_kernel_authority_row_count", 0)),
            )

        budget_family = str(
            detail_values.get("stage_budget_family")
            or getattr(self, "_kernel_budget_family", "")
        )
        # The stage-budget wrapper is installed immediately before this layer,
        # so its returned row is the authoritative budget-family observation.
        row = original_sample(
            self,
            stage,
            phase=phase,
            counts=count_values,
            details=detail_values,
            elapsed_ns=elapsed_ns,
        )
        budget = row.get("stage_budget") if isinstance(row, Mapping) else None
        if isinstance(budget, Mapping):
            budget_family = str(budget.get("stage_family") or budget_family)
        elif isinstance(row, Mapping):
            budget_family = str(
                (row.get("details") or {}).get("stage_budget_family") or budget_family
            )

        try:
            event = registry.observe(
                stage=stage,
                phase=phase,
                counts=count_values,
                details=detail_values,
                budget_family=budget_family,
            )
        except KernelContractViolation as error:
            _persist(self, error.diagnostic)
            raise
        _persist(self, event)
        row["execution_kernel_contract"] = event
        return row

    semantic.SemanticExecutionContext.sample = sample_wrapper

    # Supply handoff facts without contaminating the semantic owner or reducer.
    original_record = semantic.ClosureOwnerReplayContract.record_observation_batch

    def record_observation_batch(
        self: Any,
        deltas: Any,
        *,
        owner: Any,
    ) -> None:
        context = self.context
        prior_obligations = int(
            getattr(context, "_kernel_boundary_obligation_count", 0)
        )
        current_obligations = len(getattr(owner, "_boundary_obligations", ()))
        setattr(
            context,
            "_kernel_new_durable_obligations",
            max(0, current_obligations - prior_obligations),
        )
        setattr(context, "_kernel_boundary_obligation_count", current_obligations)
        setattr(
            context,
            "_kernel_frontier_drained",
            bool(
                getattr(owner, "_producer_exhausted", False)
                and not getattr(owner, "_pending_jobs", {})
                and not getattr(owner, "_in_flight_jobs", {})
                and not getattr(owner, "_dirty_groups", set())
            ),
        )
        authority = os.environ.get("SENSIBLAW_EXECUTION_AUTHORITY", "checkpoint")
        setattr(context, "_kernel_authority_backend", authority)
        # PostgreSQL execution adapters increment this only after the admission
        # transaction commits.  Local replay deliberately leaves it zero.
        setattr(
            context,
            "_kernel_authority_row_count",
            int(getattr(context, "_postgres_admission_row_count", 0)),
        )
        setattr(
            context,
            "_kernel_durable_admissions",
            int(getattr(context, "_postgres_admission_row_count", 0)),
        )
        return original_record(self, deltas, owner=owner)

    semantic.ClosureOwnerReplayContract.record_observation_batch = (
        record_observation_batch
    )
    setattr(semantic, _INSTALL_MARKER, True)
    return True


__all__ = ["install_execution_kernel_contracts"]
