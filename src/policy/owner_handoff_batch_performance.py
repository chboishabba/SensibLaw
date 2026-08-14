"""Remove duplicate cumulative indexes from v3 closure handoff.

The bounded streaming loop already filters every activation batch against the
canonical owner's ``_observation_deltas`` before invoking
``record_observation_batch``.  The replay contract previously rebuilt a second
``recorded_delta_refs`` set before and after every batch, then serialized it into
handoff checkpoints.  That index is redundant: exact owner reconstruction
recreates ``_observation_deltas`` before new activation continues.
"""

from __future__ import annotations

from time import monotonic_ns
from typing import Any, Iterable


_INSTALL_MARKER = "_owner_handoff_batch_performance_installed"


def install_owner_handoff_batch_performance() -> bool:
    from src.policy import owner_handoff_performance as performance
    from src.policy import parallel_semantic_execution as parallel

    if getattr(parallel, _INSTALL_MARKER, False):
        return False
    if not getattr(parallel, performance._INSTALL_MARKER, False):
        raise RuntimeError(
            "batch handoff performance must install after v3 owner handoff"
        )

    def record_observation_batch(
        self: Any,
        deltas: Iterable[Any],
        *,
        owner: Any,
    ) -> None:
        started = monotonic_ns()
        # The caller has already selected deltas absent from the canonical
        # owner's observation map.  Materialize this bounded leaf exactly once;
        # do not rebuild a cumulative duplicate-membership set.
        new_deltas = tuple(deltas)
        if not new_deltas:
            self.checkpoint_owner(owner, force=True)
            return
        artifact_ref = parallel._write_replay_artifact(
            self.context,
            artifact_kind="observation_delta_batch",
            value={"deltas": [delta.to_dict() for delta in new_deltas]},
        )
        parallel._append_replay_event(
            self.context,
            artifact_kind="observation_delta_batch",
            artifact_ref=artifact_ref,
        )
        self.checkpoint_owner(owner, force=True)
        self.context.sample(
            "owner_admission_batch",
            phase="closure_handoff",
            counts={
                "rows_in": len(new_deltas),
                "pending_jobs": len(owner._pending_jobs),
                "owner_revision": owner.revision,
            },
            details={
                "checkpoint_managed": True,
                "duplicate_membership_index": False,
            },
            elapsed_ns=monotonic_ns() - started,
        )

    parallel.ClosureOwnerReplayContract.record_observation_batch = (
        record_observation_batch
    )

    # v3 no longer needs recorded_delta_refs in the hot state or checkpoint.
    original_payload = performance._compact_checkpoint_payload

    def compact_checkpoint_payload(context: Any) -> dict[str, Any]:
        payload = original_payload(context)
        payload.pop("recorded_delta_refs", None)
        # checkpoint_ref covers the complete payload, so recalculate after
        # removing the redundant physical index.
        payload.pop("checkpoint_ref", None)
        payload["checkpoint_ref"] = "closure-handoff:" + parallel.canonical_sha256(
            payload
        )
        return payload

    performance._compact_checkpoint_payload = compact_checkpoint_payload
    setattr(parallel, _INSTALL_MARKER, True)
    return True


__all__ = ["install_owner_handoff_batch_performance"]
