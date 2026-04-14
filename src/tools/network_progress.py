from __future__ import annotations

import os
import sys
import time
from typing import Any, Callable, Mapping


ProgressCallback = Callable[[str, Mapping[str, Any]], None]

_FALSEY = {"0", "false", "no", "off"}


def fetch_progress_enabled(env_var: str = "ITIR_FETCH_PROGRESS") -> bool:
    raw = os.environ.get(env_var, "").strip().lower()
    if not raw:
        return True
    return raw not in _FALSEY


def format_byte_count(value: int | float | None) -> str:
    if value is None:
        return "?"
    amount = float(max(0.0, float(value)))
    units = ("B", "KB", "MB", "GB", "TB")
    unit_index = 0
    while amount >= 1024.0 and unit_index < len(units) - 1:
        amount /= 1024.0
        unit_index += 1
    if unit_index == 0:
        return f"{int(amount)}{units[unit_index]}"
    return f"{amount:.1f}{units[unit_index]}"


def format_duration(seconds: float | int | None) -> str:
    if seconds is None:
        return "?"
    total = max(0, int(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def build_transfer_status_line(
    *,
    label: str,
    downloaded_bytes: int,
    total_bytes: int | None,
    started_monotonic: float,
    status: str,
) -> tuple[str, dict[str, Any]]:
    now = time.monotonic()
    elapsed_s = max(0.001, now - started_monotonic)
    speed_bps = downloaded_bytes / elapsed_s
    eta_s = None
    percent = None
    if total_bytes and total_bytes > 0:
        remaining = max(0, total_bytes - downloaded_bytes)
        eta_s = remaining / speed_bps if speed_bps > 0 else None
        percent = min(100.0, (downloaded_bytes / total_bytes) * 100.0)

    progress_bits = [f"status={status}", f"elapsed={format_duration(elapsed_s)}"]
    if percent is not None:
        progress_bits.append(f"done={percent:5.1f}%")
    progress_bits.append(
        f"bytes={format_byte_count(downloaded_bytes)}/{format_byte_count(total_bytes)}"
    )
    progress_bits.append(f"speed={format_byte_count(speed_bps)}/s")
    progress_bits.append(f"eta={format_duration(eta_s)}")
    line = f"[fetch] {label} " + " ".join(progress_bits)
    details = {
        "label": label,
        "status": status,
        "elapsed_s": round(elapsed_s, 3),
        "downloaded_bytes": int(downloaded_bytes),
        "total_bytes": int(total_bytes) if total_bytes is not None else None,
        "speed_bytes_per_s": round(speed_bps, 3),
        "eta_s": None if eta_s is None else round(eta_s, 3),
        "percent": None if percent is None else round(percent, 3),
    }
    return line, details


def stderr_progress_callback(stage: str, details: Mapping[str, Any]) -> None:
    label = str(details.get("label") or "").strip() or "network"
    downloaded = int(details.get("downloaded_bytes") or 0)
    total = details.get("total_bytes")
    total_value = int(total) if total is not None else None
    started = float(details.get("started_monotonic") or time.monotonic())
    line, _ = build_transfer_status_line(
        label=label,
        downloaded_bytes=downloaded,
        total_bytes=total_value,
        started_monotonic=started,
        status=stage,
    )
    print(line, file=sys.stderr, flush=True)


class TransferProgressReporter:
    def __init__(
        self,
        *,
        label: str,
        total_bytes: int | None = None,
        callback: ProgressCallback | None = None,
        enabled: bool | None = None,
        interval_s: float = 1.0,
    ) -> None:
        self.label = label
        self.total_bytes = total_bytes
        self.callback = callback or stderr_progress_callback
        self.enabled = fetch_progress_enabled() if enabled is None else enabled
        self.interval_s = max(0.1, float(interval_s))
        self.started_monotonic = time.monotonic()
        self.last_emit_monotonic = 0.0

    def _emit(self, stage: str, downloaded_bytes: int, *, force: bool = False) -> None:
        if not self.enabled:
            return
        now = time.monotonic()
        if not force and self.last_emit_monotonic and (now - self.last_emit_monotonic) < self.interval_s:
            return
        details = {
            "label": self.label,
            "downloaded_bytes": int(downloaded_bytes),
            "total_bytes": self.total_bytes,
            "started_monotonic": self.started_monotonic,
        }
        self.callback(stage, details)
        self.last_emit_monotonic = now

    def start(self) -> None:
        self._emit("starting", 0, force=True)

    def update(self, downloaded_bytes: int) -> None:
        self._emit("downloading", downloaded_bytes)

    def finish(self, downloaded_bytes: int) -> dict[str, Any]:
        self._emit("complete", downloaded_bytes, force=True)
        _, details = build_transfer_status_line(
            label=self.label,
            downloaded_bytes=downloaded_bytes,
            total_bytes=self.total_bytes,
            started_monotonic=self.started_monotonic,
            status="complete",
        )
        return details
