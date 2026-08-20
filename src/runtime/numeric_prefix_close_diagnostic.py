"""Diagnostic stop control for genuine committed numeric sentence prefixes.

The performance probe needs real sentence-close transactions, but it must not pay
for an entire document merely to inspect a few early close positions.  This module
provides an opt-in control-plane boundary: after the configured number of sentence
closures has *committed*, the worker emits an fsynced receipt and raises a typed
signal.  The signal is diagnostic completion, not semantic failure.

No production behavior changes unless ``SENSIBLAW_SENTENCE_PREFIX_STOP_AFTER`` is
set.  The companion output path is mandatory so an interrupted outer harness can
still distinguish a deliberate prefix stop from a crash.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
import os
from pathlib import Path
from typing import Any, Mapping


PREFIX_CLOSE_DIAGNOSTIC_REF = "sensiblaw.numeric-prefix-close-diagnostic.v0_1"
STOP_AFTER_ENV = "SENSIBLAW_SENTENCE_PREFIX_STOP_AFTER"
STOP_OUTPUT_ENV = "SENSIBLAW_SENTENCE_PREFIX_STOP_OUTPUT"


class NumericPrefixDiagnosticComplete(RuntimeError):
    """Raised only after the requested sentence prefix has durably committed."""


@dataclass(frozen=True, slots=True)
class PrefixCloseDiagnosticConfig:
    stop_after_committed: int
    output_path: Path


def prefix_close_diagnostic_config() -> PrefixCloseDiagnosticConfig | None:
    raw = os.environ.get(STOP_AFTER_ENV, "").strip()
    if not raw:
        return None
    stop_after = int(raw)
    if stop_after < 1:
        raise ValueError(f"{STOP_AFTER_ENV} must be positive")
    output_raw = os.environ.get(STOP_OUTPUT_ENV, "").strip()
    if not output_raw:
        raise ValueError(f"{STOP_OUTPUT_ENV} is required when {STOP_AFTER_ENV} is set")
    return PrefixCloseDiagnosticConfig(
        stop_after_committed=stop_after,
        output_path=Path(output_raw),
    )


def _append_jsonl(path: Path, record: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.write(descriptor, payload)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def record_prefix_close_completion(
    config: PrefixCloseDiagnosticConfig,
    *,
    run_ref: str,
    worker_ref: str,
    committed_sentence_closes: int,
    work_id: int,
    region_id: int,
    released_unstarted_leases: int,
) -> None:
    """Persist proof that the requested prefix boundary was crossed after commit."""

    if committed_sentence_closes < config.stop_after_committed:
        raise ValueError(
            "prefix completion cannot be recorded before its stop boundary"
        )
    _append_jsonl(
        config.output_path,
        {
            "contract_ref": PREFIX_CLOSE_DIAGNOSTIC_REF,
            "recorded_at": datetime.now(UTC).isoformat(),
            "pid": os.getpid(),
            "run_ref": run_ref,
            "worker_ref": worker_ref,
            "stop_after_committed": config.stop_after_committed,
            "committed_sentence_closes": committed_sentence_closes,
            "last_committed_work_id": int(work_id),
            "last_committed_region_id": int(region_id),
            "released_unstarted_leases": int(released_unstarted_leases),
            "semantic_state": (
                "selected sentence close transaction committed normally; remaining "
                "preleased but unstarted sentence fibres were returned to READY"
            ),
        },
    )


__all__ = [
    "NumericPrefixDiagnosticComplete",
    "PREFIX_CLOSE_DIAGNOSTIC_REF",
    "PrefixCloseDiagnosticConfig",
    "STOP_AFTER_ENV",
    "STOP_OUTPUT_ENV",
    "prefix_close_diagnostic_config",
    "record_prefix_close_completion",
]
