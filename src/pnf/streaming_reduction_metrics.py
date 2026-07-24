"""Execution-only instrumentation for keyed fibre reductions.

The fixed-point owner remains the semantic authority. This module records each
reduction wave and aggregates its metrics without changing proposal, factor,
graph, ledger, or fixed-point identities.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Iterable, Mapping

from src.pnf.factor_proposals import ProposalReduction
from src.pnf.streaming_fixed_point import StreamingSemanticOwner
from src.policy.carriers.canonical import canonical_sha256
from src.runtime.stage_timing import StageHandle

_INSTALLED = False


def _aggregate_metrics(reductions: Iterable[ProposalReduction]) -> dict[str, Any]:
    rows = tuple(reductions)
    bucket_count = sum(int(row.metrics.get("bucket_count") or 0) for row in rows)
    largest_bucket = max(
        (int(row.metrics.get("largest_bucket") or 0) for row in rows),
        default=0,
    )
    comparisons = sum(
        int(row.metrics.get("candidate_comparisons") or 0) for row in rows
    )
    potential = sum(
        int(row.metrics.get("potential_candidate_comparisons") or 0)
        for row in rows
    )
    avoided = sum(int(row.metrics.get("comparisons_avoided") or 0) for row in rows)
    duplicates = sum(
        int(row.metrics.get("duplicates_collapsed") or 0) for row in rows
    )
    alternatives = sum(
        int(row.metrics.get("alternatives_retained") or 0) for row in rows
    )
    factor_count = sum(len(row.factors) for row in rows)
    deduplicated_proposals = sum(
        max(0, row.proposal_count - row.deduplicated_count) for row in rows
    )
    return {
        "bucket_count": bucket_count,
        "largest_bucket": largest_bucket,
        "candidate_comparisons": comparisons,
        "potential_candidate_comparisons": potential,
        "comparisons_avoided": avoided,
        "comparison_avoidance_ratio": avoided / potential if potential else 1.0,
        "duplicates_collapsed": duplicates,
        "alternatives_retained": alternatives,
        "factor_count": factor_count,
        "reduction_ratio": (
            factor_count / deduplicated_proposals if deduplicated_proposals else 0.0
        ),
    }


def install_streaming_reduction_metrics() -> None:
    """Install idempotent execution instrumentation on the owner and timer."""

    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    original_reduce = StreamingSemanticOwner.reduce_dirty_groups
    original_materialized = StreamingSemanticOwner.materialized_reduction.fget
    original_to_dict = StreamingSemanticOwner.to_dict
    original_finish = StageHandle.finish
    base_metrics_by_document: dict[str, Mapping[str, Any]] = {}

    def instrumented_reduce(self: StreamingSemanticOwner):
        dirty_keys = tuple(sorted(self._dirty_groups))
        stage_refs = {
            self._proposal_stage[proposal.proposal_ref]
            for key in dirty_keys
            for proposal in self._proposals.values()
            if self.proposal_owner_key(proposal) == key
            and proposal.proposal_ref in self._proposal_stage
        }
        state_delta = original_reduce(self)
        reductions = tuple(
            self._reductions[key] for key in dirty_keys if key in self._reductions
        )
        if reductions:
            metrics = _aggregate_metrics(reductions)
            stage = (
                next(iter(stage_refs))
                if len(stage_refs) == 1
                else "mixed"
                if stage_refs
                else "unknown"
            )
            history = list(getattr(self, "_reduction_history", ()))
            payload = {
                "document_ref": self.document_ref,
                "sequence_no": len(history),
                "revision": self.revision,
                "stage": stage,
                "owner_refs": [key.owner_ref for key in dirty_keys],
                "metrics": metrics,
                "authority": "execution_telemetry_only",
                "semantic_identity_effect": "none",
            }
            history.append(
                {
                    "reduction_receipt_ref": "reduction-execution-receipt:"
                    + canonical_sha256(payload),
                    **payload,
                }
            )
            self._reduction_history = history
            if stage == "base":
                base_metrics_by_document[self.document_ref] = metrics
        return state_delta

    def materialized_with_metrics(self: StreamingSemanticOwner) -> ProposalReduction:
        if original_materialized is None:
            raise RuntimeError("streaming owner materialized reduction is unavailable")
        reduction = original_materialized(self)
        return ProposalReduction(
            document_ref=reduction.document_ref,
            factors=reduction.factors,
            residuals=reduction.residuals,
            proposal_count=reduction.proposal_count,
            deduplicated_count=reduction.deduplicated_count,
            metrics=_aggregate_metrics(self._reductions.values()),
        )

    def to_dict_with_history(self: StreamingSemanticOwner) -> dict[str, Any]:
        payload = original_to_dict(self)
        payload["reduction_history"] = [
            dict(row) for row in getattr(self, "_reduction_history", ())
        ]
        return payload

    def finish_with_reduction_metrics(self: StageHandle):
        timing = original_finish(self)
        if self.stage != "base_proposal_reduction":
            return timing
        metrics = base_metrics_by_document.get(self.ledger.document_ref)
        if not metrics:
            return timing
        updated = replace(
            timing,
            details={**dict(timing.details), "fibre_partition_metrics": dict(metrics)},
        )
        if self.ledger.timings and self.ledger.timings[-1] is timing:
            self.ledger.timings[-1] = updated
        return updated

    StreamingSemanticOwner.reduce_dirty_groups = instrumented_reduce
    StreamingSemanticOwner.materialized_reduction = property(materialized_with_metrics)
    StreamingSemanticOwner.to_dict = to_dict_with_history
    StageHandle.finish = finish_with_reduction_metrics


__all__ = ["install_streaming_reduction_metrics"]
