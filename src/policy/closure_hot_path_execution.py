"""Execution-only acceleration for bounded semantic closure.

The semantic owner and reducers remain authoritative. This module fixes two
physical pathologies exposed by the live GWB replay:

* the bounded executor retained a stale import of ``solve_operator_job`` and
  therefore bypassed the process-backed wrapper installed by
  :mod:`parallel_typing_tail`, leaving CPU-bound stage-7 work under the GIL;
* every completed immutable closure receipt immediately re-reduced complete
  owner fibres even while other pure jobs from the same frontier were still in
  flight.

No proposal identity, reduction rule, owner key, or final materialized graph is
changed. Reduction coalescing is fail-closed: it is allowed only while another
job is in flight and every currently dirty proposal has an empty
``dependency_factor_refs`` declaration. A dependency-bearing fibre always uses
the original eager reducer.
"""

from __future__ import annotations

import os
from typing import Any


_INSTALL_MARKER = "_closure_hot_path_execution_installed"
_DEFAULT_AUTO_PROCESS_CAP = 4


def _positive_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    value = int(raw)
    if value < 1:
        raise ValueError(f"{name} must be positive")
    return value


def auto_semantic_process_workers() -> int:
    """Return the default process width when the user supplied no override."""

    explicit = os.environ.get("SENSIBLAW_SEMANTIC_PROCESS_WORKERS")
    if explicit is not None and explicit.strip():
        value = int(explicit)
        if value < 1:
            raise ValueError("SENSIBLAW_SEMANTIC_PROCESS_WORKERS must be positive")
        return value
    available = max(1, int(os.cpu_count() or 1))
    cap = _positive_int(
        "SENSIBLAW_SEMANTIC_PROCESS_AUTO_MAX", _DEFAULT_AUTO_PROCESS_CAP
    )
    return max(1, min(available, cap))


def _dirty_proposals_are_dependency_free(owner: Any) -> bool:
    """Certify the narrow execution condition used for reduction coalescing."""

    for key in tuple(owner._dirty_groups):
        proposals = owner._proposals_by_owner.get(key, {})
        if any(proposal.dependency_factor_refs for proposal in proposals.values()):
            return False
    return True


def install_closure_hot_path_execution() -> bool:
    """Install multicore closure dispatch and dependency-free reduction waves."""

    from src.policy import bounded_operational_execution as bounded
    from src.policy import operational_corpus_compilation as operational

    if getattr(bounded, _INSTALL_MARKER, False):
        return False

    # One execution-width source of truth. Setting the environment only when it
    # was absent keeps explicit operator configuration authoritative while also
    # ensuring activation buffering and the process-pool helper observe the same
    # auto-selected width.
    os.environ.setdefault(
        "SENSIBLAW_SEMANTIC_PROCESS_WORKERS",
        str(auto_semantic_process_workers()),
    )

    # ``bounded_operational_execution`` imported the original function before
    # ``parallel_typing_tail`` replaced the operational module global. Rebind
    # the bounded module to the already-installed process-aware wrapper.
    bounded.solve_operator_job = operational.solve_operator_job

    owner_class = bounded.BoundedStreamingSemanticOwner
    original_reduce_dirty_groups = owner_class.reduce_dirty_groups

    def reduce_dirty_groups(self: Any):
        # Solver jobs are immutable and execute without access to owner state.
        # While another job from the same leased frontier is still running, an
        # intermediate reduction cannot affect that job. For dependency-free
        # proposals the eventual full-fibre reduction over the union is exactly
        # the same canonical reducer the eager path would run after the final
        # receipt, so defer the repeated scans until the frontier drains.
        if (
            self._dirty_groups
            and self._in_flight_jobs
            and _dirty_proposals_are_dependency_free(self)
        ):
            counts = getattr(self, "_kernel_counts", None)
            if counts is not None:
                counts["dependency_free_reductions_coalesced"] += 1
                counts["dependency_free_dirty_groups_deferred"] += len(
                    self._dirty_groups
                )
            return self._advance(prior_revision=self.revision)
        return original_reduce_dirty_groups(self)

    owner_class.reduce_dirty_groups = reduce_dirty_groups
    setattr(bounded, _INSTALL_MARKER, True)
    return True


__all__ = [
    "auto_semantic_process_workers",
    "install_closure_hot_path_execution",
]
