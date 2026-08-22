"""Coalesce duplicate process-tree RSS reads inside one scheduling burst.

The bounded scheduler samples resources for pressure control, while receipt
progress reporting immediately samples the same process tree again.  Walking
``/proc`` recursively for every tiny closure receipt can become measurable on a
large document.  A few milliseconds of telemetry reuse does not change semantic
state and remains far below the scheduler's resource-response timescale.
"""

from __future__ import annotations

import os
from time import monotonic_ns
from typing import Callable


_INSTALL_MARKER = "_resource_sampling_hot_path_execution_installed"
_DEFAULT_CACHE_MILLIS = 5


def _cache_ns() -> int:
    raw = os.environ.get(
        "SENSIBLAW_PROCESS_TREE_RSS_CACHE_MILLIS",
        str(_DEFAULT_CACHE_MILLIS),
    )
    try:
        millis = int(raw)
    except ValueError as error:
        raise ValueError(
            "SENSIBLAW_PROCESS_TREE_RSS_CACHE_MILLIS must be an integer"
        ) from error
    if millis < 0:
        raise ValueError("SENSIBLAW_PROCESS_TREE_RSS_CACHE_MILLIS cannot be negative")
    return millis * 1_000_000


def cached_sampler(
    sample: Callable[[], int],
    *,
    ttl_ns: int,
) -> Callable[[], int]:
    last_ns = -1
    last_value = 0

    def current() -> int:
        nonlocal last_ns, last_value
        now = monotonic_ns()
        if last_ns >= 0 and now - last_ns <= ttl_ns:
            return last_value
        last_value = int(sample())
        last_ns = now
        return last_value

    return current


def install_resource_sampling_hot_path_execution() -> bool:
    from src.policy import bounded_operational_execution as bounded

    if getattr(bounded, _INSTALL_MARKER, False):
        return False
    ttl_ns = _cache_ns()
    if ttl_ns:
        bounded.current_process_tree_rss_bytes = cached_sampler(
            bounded.current_process_tree_rss_bytes,
            ttl_ns=ttl_ns,
        )
    setattr(bounded, _INSTALL_MARKER, True)
    return True


__all__ = [
    "cached_sampler",
    "install_resource_sampling_hot_path_execution",
]
