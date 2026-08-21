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
import fcntl
import json
import os
from pathlib import Path
from typing import Any, Mapping


PREFIX_CLOSE_DIAGNOSTIC_REF = "sensiblaw.numeric-prefix-close-diagnostic.v0_1"
STOP_AFTER_ENV = "SENSIBLAW_SENTENCE_PREFIX_STOP_AFTER"
STOP_OUTPUT_ENV = "SENSIBLAW_SENTENCE_PREFIX_STOP_OUTPUT"
STOP_STATE_ENV = "SENSIBLAW_SENTENCE_PREFIX_STOP_STATE"
_PREFIX_CLOSE_STATE_REF = "sensiblaw.numeric-prefix-close-diagnostic-state.v0_1"


class NumericPrefixDiagnosticComplete(RuntimeError):
    """Raised only after the requested sentence prefix has durably committed."""


@dataclass(frozen=True, slots=True)
class PrefixCloseDiagnosticConfig:
    stop_after_committed: int
    output_path: Path
    state_path: Path


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
    output_path = Path(output_raw)
    state_raw = os.environ.get(STOP_STATE_ENV, "").strip()
    return PrefixCloseDiagnosticConfig(
        stop_after_committed=stop_after,
        output_path=output_path,
        state_path=(
            Path(state_raw)
            if state_raw
            else output_path.with_name(f"{output_path.name}.state.json")
        ),
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


def record_committed_prefix_close(config: PrefixCloseDiagnosticConfig) -> int:
    """Durably count a post-commit close across every diagnostic process.

    A strict serial worker may be replaced by another Python process during one
    run.  The counter therefore cannot live in a closure-local dictionary.  An
    attempted count beyond the requested boundary fails closed: that would mean
    the diagnostic did not stop at the exact committed prefix it claims.
    """

    config.state_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(config.state_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        os.lseek(descriptor, 0, os.SEEK_SET)
        raw = os.read(descriptor, 65_536)
        if raw:
            try:
                state = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise RuntimeError(
                    "numeric prefix diagnostic state is unreadable"
                ) from error
            if (
                state.get("contract_ref") != _PREFIX_CLOSE_STATE_REF
                or state.get("stop_after_committed") != config.stop_after_committed
            ):
                raise RuntimeError(
                    "numeric prefix diagnostic state belongs to another run"
                )
            previous = state.get("committed_sentence_closes")
            if not isinstance(previous, int) or previous < 0:
                raise RuntimeError("numeric prefix diagnostic state is invalid")
        else:
            previous = 0
        committed = previous + 1
        if committed > config.stop_after_committed:
            raise RuntimeError(
                "numeric prefix diagnostic committed beyond its requested boundary"
            )
        payload = json.dumps(
            {
                "committed_sentence_closes": committed,
                "contract_ref": _PREFIX_CLOSE_STATE_REF,
                "stop_after_committed": config.stop_after_committed,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        os.lseek(descriptor, 0, os.SEEK_SET)
        os.ftruncate(descriptor, 0)
        os.write(descriptor, payload)
        os.fsync(descriptor)
        return committed
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
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
    "STOP_STATE_ENV",
    "prefix_close_diagnostic_config",
    "record_committed_prefix_close",
    "record_prefix_close_completion",
]
