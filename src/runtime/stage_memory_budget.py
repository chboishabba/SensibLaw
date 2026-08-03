"""Proactive memory budgets for document compiler stage boundaries.

The global process limit remains the final safety net.  These lower stage-local
budgets make pressure visible before one stage consumes all remaining headroom
and record a durable transition receipt for restart and capacity planning.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
import os
from pathlib import Path
from typing import Any, Mapping

from src.runtime.execution_resource_ledger import sample_process_resources


MIB = 1024 * 1024
GIB = 1024 * MIB
STAGE_BUDGET_SCHEMA_VERSION = "sensiblaw.stage-memory-budget.v1"


@dataclass(frozen=True)
class StageMemoryBudget:
    stage_family: str
    soft_bytes: int
    hard_bytes: int

    def __post_init__(self) -> None:
        if self.soft_bytes < 1 or self.hard_bytes <= self.soft_bytes:
            raise ValueError("stage hard budget must exceed its positive soft budget")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


DEFAULT_STAGE_BUDGETS: Mapping[str, StageMemoryBudget] = {
    "parser_projection": StageMemoryBudget("parser_projection", 3 * GIB, 4 * GIB),
    "typing": StageMemoryBudget("typing", 4 * GIB, 5 * GIB),
    "closure": StageMemoryBudget("closure", 5 * GIB, 6 * GIB),
    "finalization": StageMemoryBudget(
        "finalization", 4 * GIB, 5 * GIB + 512 * MIB
    ),
    "serialization": StageMemoryBudget("serialization", 2 * GIB, 3 * GIB),
    "publication": StageMemoryBudget("publication", 2 * GIB, 3 * GIB),
    "parity": StageMemoryBudget("parity", 1536 * MIB, 2560 * MIB),
}

_STAGE_ALIASES = {
    "parser_annotation": "parser_projection",
    "parser_observation_projection": "parser_projection",
    "local_typing_diagnostics": "typing",
    "base_proposal_generation": "closure",
    "streaming_closure": "closure",
    "closure_executor_evaluation": "closure",
    "materialize_factor_reductions": "finalization",
    "materialize_residuals": "finalization",
    "assemble_reduction": "finalization",
    "build_convergent_ledger": "finalization",
    "build_region_boundary_summaries": "finalization",
    "validate_coverage": "finalization",
    "validate_unresolved_obligations": "finalization",
    "build_fixed_point_certificate": "finalization",
    "serialize_closure_receipt": "serialization",
    "postgres_persistence": "publication",
    "acceptance_comparison": "parity",
}


class StageMemoryBudgetExceeded(RuntimeError):
    """A stage crossed its explicit hard memory budget."""

    def __init__(self, receipt: Mapping[str, Any]):
        self.receipt = dict(receipt)
        super().__init__(
            f"stage {self.receipt.get('stage')} exceeded hard memory budget"
        )


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _env_mib(name: str, default_bytes: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default_bytes
    try:
        value = int(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer MiB value") from error
    if value < 1:
        raise ValueError(f"{name} must be positive")
    return value * MIB


def stage_family(stage: str) -> str:
    normalized = str(stage).split(":", maxsplit=1)[0]
    return _STAGE_ALIASES.get(normalized, normalized)


def budget_for_stage(stage: str) -> StageMemoryBudget | None:
    family = stage_family(stage)
    default = DEFAULT_STAGE_BUDGETS.get(family)
    if default is None:
        return None
    key = family.upper().replace("-", "_")
    soft = _env_mib(f"SENSIBLAW_STAGE_{key}_SOFT_MIB", default.soft_bytes)
    hard = _env_mib(f"SENSIBLAW_STAGE_{key}_HARD_MIB", default.hard_bytes)
    return StageMemoryBudget(family, soft, hard)


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


class StageMemoryBudgetGuard:
    """Observe and enforce lower per-stage budgets with durable receipts."""

    def __init__(
        self,
        *,
        root: str | Path | None = None,
        hard_failure: bool = True,
    ) -> None:
        configured = root or os.environ.get("SENSIBLAW_RESOURCE_CHECKPOINT_DIR")
        self.root = Path(configured) / "stage-memory" if configured else None
        self.hard_failure = hard_failure
        self.sequence = 0

    def checkpoint(
        self,
        stage: str,
        *,
        phase: str,
        semantic_counts: Mapping[str, int] | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        resources = sample_process_resources()
        budget = budget_for_stage(stage)
        pss = int(resources["pss_bytes"])
        state = "unbudgeted"
        if budget is not None:
            if pss >= budget.hard_bytes:
                state = "hard_exceeded"
            elif pss >= budget.soft_bytes:
                state = "soft_pressure"
            else:
                state = "within_budget"
        receipt = {
            "schema_version": STAGE_BUDGET_SCHEMA_VERSION,
            "sequence": self.sequence,
            "stage": str(stage),
            "stage_family": stage_family(stage),
            "phase": str(phase),
            "state": state,
            "observed_at": _utc_now(),
            "resources": dict(resources),
            "budget": budget.to_dict() if budget is not None else None,
            "headroom_bytes": (
                max(0, budget.hard_bytes - pss) if budget is not None else None
            ),
            "semantic_counts": {
                str(key): int(value)
                for key, value in sorted((semantic_counts or {}).items())
            },
            "details": dict(details or {}),
        }
        self.sequence += 1
        if self.root is not None:
            self.root.mkdir(parents=True, exist_ok=True)
            _atomic_json(self.root / "latest.json", receipt)
            with (self.root / "events.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(receipt, sort_keys=True) + "\n")
        if state == "hard_exceeded" and self.hard_failure:
            raise StageMemoryBudgetExceeded(receipt)
        return receipt


__all__ = [
    "DEFAULT_STAGE_BUDGETS",
    "STAGE_BUDGET_SCHEMA_VERSION",
    "StageMemoryBudget",
    "StageMemoryBudgetExceeded",
    "StageMemoryBudgetGuard",
    "budget_for_stage",
    "stage_family",
]
