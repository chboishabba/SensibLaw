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
* strict numeric token COPY omitted already-determined identity/edge coordinates,
  forcing persistent lookup/rewrite work after producer-complete parsing;
* durable sentence/adjacent work was claimed one queue row at a time even when
  the lease transition itself can be performed over a bounded exact fibre.

No proposal identity, reduction rule, owner key, sentence digest, lease fence,
or final materialized graph is changed. Diagnostic EXPLAIN hooks are opt-in and
execute the genuine statements with all active integrity machinery; ordinary
production pays no diagnostic path cost.
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
    dependency_bearing = getattr(owner, "_dependency_bearing_owner_keys", None)
    if dependency_bearing is None:
        return not any(
            proposal.dependency_factor_refs
            for key in owner._dirty_groups
            for proposal in owner._proposals_by_owner[key].values()
        )
    return not owner._dirty_groups.intersection(dependency_bearing)


def install_closure_hot_path_execution() -> bool:
    """Install multicore closure dispatch and work-conserving closure strategies."""

    from src.policy import bounded_operational_execution as bounded
    from src.policy import operational_corpus_compilation as operational
    from src.policy.bounded_sentence_batch_leasing import (
        install_bounded_sentence_batch_leasing,
    )
    from src.policy.direct_process_closure_execution import (
        install_direct_process_closure_execution,
    )
    from src.policy.live_hierarchy_close_attribution import (
        install_live_hierarchy_close_attribution,
    )
    from src.policy.live_region_close_explain import install_live_region_close_explain
    from src.policy.live_token_insert_explain import install_live_token_insert_explain
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

    os.environ.setdefault(
        "SENSIBLAW_SEMANTIC_PROCESS_WORKERS",
        str(auto_semantic_process_workers()),
    )
    bounded.solve_operator_job = operational.solve_operator_job

    owner_class = bounded.BoundedStreamingSemanticOwner
    original_index_proposal = owner_class._index_proposal
    original_reduce_dirty_groups = owner_class.reduce_dirty_groups

    def index_proposal(self: Any, proposal: Any, *, stage: str):
        indexed = original_index_proposal(self, proposal, stage=stage)
        if indexed is not None and proposal.dependency_factor_refs:
            _proposal_ref, key = indexed
            dependency_bearing = getattr(self, "_dependency_bearing_owner_keys", None)
            if dependency_bearing is None:
                dependency_bearing = set()
                self._dependency_bearing_owner_keys = dependency_bearing
            dependency_bearing.add(key)
            counts = getattr(self, "_kernel_counts", None)
            if counts is not None:
                counts["dependency_bearing_owner_keys_indexed"] += 1
        return indexed

    def reduce_dirty_groups(self: Any):
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

    install_direct_process_closure_execution()

    # Install the optional token INSERT observer before the numeric parser hot
    # path captures _copy_rows.  The hot-path enrichment then passes its final
    # producer-complete sentence/token/head coordinates through the probe.
    install_live_token_insert_explain()
    install_numeric_parser_projection_hot_path()

    install_reusable_numeric_sentence_staging()
    install_live_region_close_explain()
    # Parent hierarchy closes use a separate store seam from sentence admission.
    # The diagnostic wrapper is inert unless its RegionKind selector is enabled.
    install_live_hierarchy_close_attribution()
    install_bounded_sentence_batch_leasing()
    install_producer_native_sentence_provenance()

    setattr(bounded, _INSTALL_MARKER, True)
    return True


__all__ = ["auto_semantic_process_workers", "install_closure_hot_path_execution"]
