"""Independent disk-pressure accounting for compiler checkpoints.

Memory and disk are separate resources.  Cleanup is conservative: the only
copy of an authoritative reusable checkpoint is never removed automatically.
Derived or diagnostic artifacts may be reclaimed only after a durable successor
is registered.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
import json
import os
from pathlib import Path
from time import time_ns
from typing import Any, Iterable, Mapping


CHECKPOINT_RETENTION_SCHEMA_VERSION = "sensiblaw.checkpoint-retention.v1"
MIB = 1024 * 1024
GIB = 1024 * MIB


class ArtifactRetentionClass(StrEnum):
    AUTHORITATIVE_REUSABLE = "authoritative_reusable"
    DERIVED_REPRODUCIBLE = "derived_reproducible"
    DIAGNOSTIC = "diagnostic"
    FAILED_ATTEMPT_TEMPORARY = "failed_attempt_temporary"


@dataclass(frozen=True)
class CheckpointArtifact:
    path: str
    retention_class: ArtifactRetentionClass
    byte_count: int
    successor_ref: str | None = None
    content_ref: str | None = None
    created_ns: int = 0

    @property
    def reclaimable(self) -> bool:
        return (
            self.retention_class != ArtifactRetentionClass.AUTHORITATIVE_REUSABLE
            and self.successor_ref is not None
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["retention_class"] = self.retention_class.value
        payload["reclaimable"] = self.reclaimable
        return payload


def _disk_budget_bytes() -> int:
    raw = os.environ.get("SENSIBLAW_CHECKPOINT_DISK_BUDGET_MIB")
    if raw is None or not raw.strip():
        return 8 * GIB
    try:
        value = int(raw)
    except ValueError as error:
        raise ValueError(
            "SENSIBLAW_CHECKPOINT_DISK_BUDGET_MIB must be an integer"
        ) from error
    if value < 1:
        raise ValueError("checkpoint disk budget must be positive")
    return value * MIB


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


class CheckpointRetentionLedger:
    """Register checkpoint ownership and reclaim only proven-derived files."""

    def __init__(self, *, root: str | Path, budget_bytes: int | None = None) -> None:
        self.root = Path(root).resolve()
        self.budget_bytes = budget_bytes or _disk_budget_bytes()
        self._artifacts: dict[str, CheckpointArtifact] = {}

    @property
    def ledger_path(self) -> Path:
        return self.root / "checkpoint-retention.json"

    def register(
        self,
        path: str | Path,
        *,
        retention_class: ArtifactRetentionClass,
        successor_ref: str | None = None,
        content_ref: str | None = None,
    ) -> CheckpointArtifact:
        target = Path(path).resolve()
        try:
            target.relative_to(self.root)
        except ValueError as error:
            raise ValueError(
                "checkpoint path must remain below retention root"
            ) from error
        artifact = CheckpointArtifact(
            path=str(target),
            retention_class=retention_class,
            byte_count=target.stat().st_size if target.exists() else 0,
            successor_ref=successor_ref,
            content_ref=content_ref,
            created_ns=time_ns(),
        )
        self._artifacts[str(target)] = artifact
        self.write()
        return artifact

    def mark_superseded(self, path: str | Path, *, successor_ref: str) -> None:
        key = str(Path(path).resolve())
        current = self._artifacts.get(key)
        if current is None:
            raise KeyError(key)
        self._artifacts[key] = CheckpointArtifact(
            path=current.path,
            retention_class=current.retention_class,
            byte_count=current.byte_count,
            successor_ref=successor_ref,
            content_ref=current.content_ref,
            created_ns=current.created_ns,
        )
        self.write()

    def extend(self, artifacts: Iterable[CheckpointArtifact]) -> None:
        for artifact in artifacts:
            self._artifacts[str(Path(artifact.path).resolve())] = artifact
        self.write()

    def report(self) -> dict[str, Any]:
        by_class = {
            value.value: {"artifact_count": 0, "byte_count": 0}
            for value in ArtifactRetentionClass
        }
        active_bytes = 0
        reclaimable_bytes = 0
        for artifact in self._artifacts.values():
            row = by_class[artifact.retention_class.value]
            row["artifact_count"] += 1
            row["byte_count"] += artifact.byte_count
            active_bytes += artifact.byte_count
            if artifact.reclaimable:
                reclaimable_bytes += artifact.byte_count
        return {
            "schema_version": CHECKPOINT_RETENTION_SCHEMA_VERSION,
            "root": str(self.root),
            "budget_bytes": self.budget_bytes,
            "active_bytes": active_bytes,
            "reclaimable_bytes": reclaimable_bytes,
            "over_budget_bytes": max(0, active_bytes - self.budget_bytes),
            "within_budget": active_bytes <= self.budget_bytes,
            "by_class": by_class,
            "artifacts": [
                self._artifacts[key].to_dict() for key in sorted(self._artifacts)
            ],
        }

    def reclaim(self, *, required_bytes: int | None = None) -> dict[str, Any]:
        report = self.report()
        target = (
            required_bytes
            if required_bytes is not None
            else int(report["over_budget_bytes"])
        )
        if target <= 0:
            return {"reclaimed_bytes": 0, "removed": [], "report": report}
        priority = {
            ArtifactRetentionClass.FAILED_ATTEMPT_TEMPORARY: 0,
            ArtifactRetentionClass.DIAGNOSTIC: 1,
            ArtifactRetentionClass.DERIVED_REPRODUCIBLE: 2,
            ArtifactRetentionClass.AUTHORITATIVE_REUSABLE: 3,
        }
        candidates = sorted(
            (row for row in self._artifacts.values() if row.reclaimable),
            key=lambda row: (
                priority[row.retention_class],
                row.created_ns,
                row.path,
            ),
        )
        reclaimed = 0
        removed: list[str] = []
        for artifact in candidates:
            if reclaimed >= target:
                break
            path = Path(artifact.path)
            try:
                path.unlink(missing_ok=True)
            except OSError:
                continue
            reclaimed += artifact.byte_count
            removed.append(artifact.path)
            self._artifacts.pop(artifact.path, None)
        self.write()
        return {
            "reclaimed_bytes": reclaimed,
            "removed": removed,
            "report": self.report(),
        }

    def write(self) -> None:
        _atomic_json(self.ledger_path, self.report())


__all__ = [
    "ArtifactRetentionClass",
    "CHECKPOINT_RETENTION_SCHEMA_VERSION",
    "CheckpointArtifact",
    "CheckpointRetentionLedger",
]
