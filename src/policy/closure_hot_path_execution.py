"""Execution-only acceleration for bounded semantic closure.

The semantic owner and reducers remain authoritative. This module fixes physical
pathologies exposed by live corpus replay while preserving semantic closure:

* the bounded executor retained a stale import of ``solve_operator_job`` and
  therefore bypassed the process-backed wrapper installed by
  :mod:`parallel_typing_tail`, leaving CPU-bound stage-7 work under the GIL;
* every completed immutable closure receipt immediately re-reduced complete
  owner fibres even while other pure jobs from the same frontier were still in
  flight;
* strict numeric sentence closure recreated and dropped five PostgreSQL temp
  staging relations for every sentence even though those relations are purely
  physical session-local carriers;
* strict sentence demands were inserted set-wise and then immediately
  reconstructed one-by-one by the generic occurrence-provenance trigger even
  though the complete producer fibre was still available;
* strict numeric token COPY omitted the already-determined sentence id, forcing
  migration 042 to execute one sentence lookup per token.

No proposal identity, reduction rule, owner key, sentence digest, lease fence,
or final materialized graph is changed. Reduction coalescing is fail-closed: it
is allowed only while another job is in flight and every currently dirty
proposal has an empty ``dependency_factor_refs`` declaration. A dependency-
bearing fibre always uses the original eager reducer. Numeric sentence staging
reuse likewise retains the existing per-sentence transaction/failure boundary;
it changes only temporary relation lifetime. Producer-native provenance retains
the generic trigger for non-sentence producers and projects the same strict
sentence provenance from the already-materialized bounded producer fibre. The
numeric parser COPY enrichment supplies the exact existing sentence identity and
leaves migration 042 as the compatibility/fail-closed authority for writers that
do not provide it.
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
    """Check the incrementally maintained dependency-bearing owner index."""

    dependency_bearing = getattr(owner, "_dependency_bearing_owner_keys", ())
    return not owner._dirty_groups.intersection(dependency_bearing)


def install_closure_hot_path_execution() -> bool:
    """Install multicore closure dispatch and work-conserving closure strategies."""

    from src.policy import bounded_operational_execution as bounded
    from src.policy import operational_corpus_compilation as operational
    from src.policy.direct_process_closure_execution import (
        install_direct_process_closure_execution,
    )
    from src.policy.numeric_parser_projection_hot_path import (
        install_numeric_parser_projection_hot_path,
    )
    from src.policy.producer_native_sentence_provenance import (
        install_producer_native_sentence_provenance,
    )
    from src.policy.reusable_numeric_sentence_staging import (
        install_reusable_numeric_sentence_staging,
    )

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
    original_index_proposal = owner_class._index_proposal
    original_reduce_dirty_groups = owner_class.reduce_dirty_groups

    def index_proposal(self: Any, proposal: Any, *, stage: str):
        indexed = original_index_proposal(self, proposal, stage=stage)
        if indexed is not None and proposal.dependency_factor_refs:
            _proposal_ref, key = indexed
            dependency_bearing = getattr(
                self,
                "_dependency_bearing_owner_keys",
                None,
            )
            if dependency_bearing is None:
                dependency_bearing = set()
                self._dependency_bearing_owner_keys = dependency_bearing
            dependency_bearing.add(key)
            counts = getattr(self, "_kernel_counts", None)
            if counts is not None:
                counts["dependency_bearing_owner_keys_indexed"] += 1
        return indexed

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

    owner_class._index_proposal = index_proposal
    owner_class.reduce_dirty_groups = reduce_dirty_groups
    # The bounded scheduler no longer needs a thread whose only job is to submit
    # the same immutable work to the semantic process pool and block on it.
    install_direct_process_closure_execution()
    # Numeric parser projection already has the exact sentence-ref fibre after
    # the sentence COPY. Resolve that finite map once and include sentence_id in
    # token COPY rows so migration 042 does not re-query it per token.
    install_numeric_parser_projection_hot_path()
    # Strict numeric sentence closure is another closure execution lane. Its
    # five temp stages contain no semantic identity and are safe to reuse across
    # sentence transactions; keep sentence atomicity/fencing otherwise intact.
    install_reusable_numeric_sentence_staging()
    # The strict producer still has the exact factor/support/slot fibre when it
    # inserts demands. Preserve that information set-wise instead of asking the
    # generic row trigger to recover the producer independently for every row.
    install_producer_native_sentence_provenance()
    setattr(bounded, _INSTALL_MARKER, True)
    return True


__all__ = [
    "auto_semantic_process_workers",
    "install_closure_hot_path_execution",
]
