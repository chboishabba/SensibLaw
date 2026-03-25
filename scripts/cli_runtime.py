from __future__ import annotations

import json
import logging
import sys
from typing import Any, Callable


ProgressCallback = Callable[[str, dict[str, Any]], None]


def configure_cli_logging(level_name: str) -> None:
    level = getattr(logging, str(level_name or "INFO").upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        stream=sys.stderr,
        format="[%(levelname)s] %(name)s: %(message)s",
        force=True,
    )


def build_progress_callback(*, enabled: bool, fmt: str = "human") -> ProgressCallback | None:
    if not enabled:
        return None
    if fmt == "json":
        return _json_progress
    if fmt == "bar":
        return _build_bar_progress_callback()
    return _human_progress


def _json_progress(stage: str, details: dict[str, Any]) -> None:
    payload = {"stage": stage, **details}
    print(json.dumps(payload, sort_keys=True), file=sys.stderr, flush=True)


def _human_progress(stage: str, details: dict[str, Any]) -> None:
    section = str(details.get("section") or "").strip()
    completed = details.get("completed")
    total = details.get("total")
    elapsed = details.get("elapsed_seconds")
    rate = details.get("items_per_second")
    eta = details.get("eta_seconds_remaining")
    interval = details.get("eta_confidence_interval_seconds")
    confidence = str(details.get("eta_confidence") or "").strip()
    message = str(details.get("message") or "").strip()
    status = str(details.get("status") or "").strip()

    parts: list[str] = [f"[progress] {stage}"]
    if section:
        parts.append(f"section={section}")
    if completed is not None and total is not None:
        parts.append(f"{completed}/{total}")
    if elapsed is not None:
        parts.append(f"elapsed={elapsed}s")
    if rate is not None:
        parts.append(f"rate={rate}/s")
    if eta is not None:
        parts.append(f"eta={eta}s")
    if interval is not None:
        parts.append(f"eta_band={interval}")
    if confidence:
        parts.append(f"eta_confidence={confidence}")
    if status:
        parts.append(f"status={status}")
    if message:
        parts.append(f"- {message}")
    print(" ".join(parts), file=sys.stderr, flush=True)


def _build_bar_progress_callback() -> ProgressCallback:
    state: dict[str, Any] = {"last_stage": None}

    def emit(stage: str, details: dict[str, Any]) -> None:
        if not sys.stderr.isatty():
            _human_progress(stage, details)
            return
        section = str(details.get("section") or stage).strip()
        completed = details.get("completed")
        total = details.get("total")
        elapsed = details.get("elapsed_seconds")
        eta = details.get("eta_seconds_remaining")
        message = str(details.get("message") or "").strip()
        status = str(details.get("status") or "").strip()

        if completed is None or total in (None, 0):
            line = f"[progress] {section} {status} {message}".strip()
            print(f"\r{line:<120}", end="", file=sys.stderr, flush=True)
            if status in {"ok", "complete", "completed"} or stage.endswith("_finished"):
                print(file=sys.stderr, flush=True)
            state["last_stage"] = stage
            return

        ratio = max(0.0, min(float(completed) / float(total), 1.0))
        width = 24
        filled = int(round(ratio * width))
        bar = "#" * filled + "-" * (width - filled)
        parts = [f"\r[{bar}] {completed}/{total}", section]
        if elapsed is not None:
            parts.append(f"elapsed={elapsed}s")
        if eta is not None:
            parts.append(f"eta={eta}s")
        if message:
            parts.append(f"- {message}")
        line = " ".join(parts)
        print(f"{line:<160}", end="", file=sys.stderr, flush=True)
        if completed >= total or stage.endswith("_finished"):
            print(file=sys.stderr, flush=True)
        state["last_stage"] = stage

    return emit
