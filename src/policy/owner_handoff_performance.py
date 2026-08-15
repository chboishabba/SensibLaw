"""Incremental hot-path execution for closure owner replay.

This module changes physical execution only. Semantic authority, proposal
identity, canonical admission order and deterministic owner reconstruction remain
unchanged.

The v2 handoff representation repeatedly copied and serialized the complete
replay-event history on every new admission. On long documents that makes the
handoff path quadratic in the number of replay events. v3 keeps the immutable
replay artifacts, appends one compact event row to a journal, and rewrites only
the small current-frontier checkpoint.
"""

from __future__ import annotations

import os
from pathlib import Path
import struct
from time import monotonic_ns
from typing import Any

from src.policy.carriers.canonical import canonical_sha256


_INSTALL_MARKER = "_owner_handoff_performance_installed"
HANDOFF_SCHEMA_VERSION = "sensiblaw.closure-handoff-state.v3"
HANDOFF_CONTRACT = "closure-owner-replay:v3"
JOURNAL_SCHEMA_VERSION = "sensiblaw.closure-handoff-journal-event.v1"
_JOURNAL_MAGIC = b"SLHJ"
_JOURNAL_HEADER = struct.Struct(">4sQBI")
_JOURNAL_DIGEST_BYTES = 32
_JOURNAL_MAX_REF_BYTES = 1024 * 1024
_JOURNAL_KIND_CODES = {
    "observation_delta": 1,
    "observation_delta_batch": 2,
    "proposal_batch": 3,
    "solver_receipt": 4,
    "dirty_reduction": 5,
}
_JOURNAL_CODE_KINDS = {value: key for key, value in _JOURNAL_KIND_CODES.items()}


def _cached_ref(instance: Any, cache_name: str, compute: Any) -> str:
    cached = instance.__dict__.get(cache_name)
    if cached is None:
        cached = str(compute())
        object.__setattr__(instance, cache_name, cached)
    return str(cached)


def _install_identity_caches() -> None:
    """Cache immutable content-addressed identities after their first use."""

    from src.pnf.factor_proposals import FactorProposal
    from src.pnf.streaming_fixed_point import (
        ObservationDelta,
        OwnerKey,
        SolverJob,
        SolverReceipt,
    )

    # These carriers are frozen and non-slotted. Their identity payload cannot
    # change after construction, so repeated canonical hashing is pure overhead.
    FactorProposal.proposal_digest = property(  # type: ignore[assignment]
        lambda self: _cached_ref(
            self,
            "_cached_proposal_digest",
            lambda: canonical_sha256(self.identity_payload()),
        )
    )
    FactorProposal.proposal_ref = property(  # type: ignore[assignment]
        lambda self: _cached_ref(
            self,
            "_cached_proposal_ref",
            lambda: "factor-proposal:" + self.proposal_digest,
        )
    )
    OwnerKey.owner_ref = property(  # type: ignore[assignment]
        lambda self: _cached_ref(
            self,
            "_cached_owner_ref",
            lambda: "semantic-owner:" + canonical_sha256(self.to_dict()),
        )
    )
    ObservationDelta.delta_ref = property(  # type: ignore[assignment]
        lambda self: _cached_ref(
            self,
            "_cached_delta_ref",
            lambda: "observation-delta:" + canonical_sha256(self.identity_payload()),
        )
    )
    SolverJob.job_ref = property(  # type: ignore[assignment]
        lambda self: _cached_ref(
            self,
            "_cached_job_ref",
            lambda: "semantic-job:" + canonical_sha256(self.identity_payload()),
        )
    )
    SolverReceipt.receipt_ref = property(  # type: ignore[assignment]
        lambda self: _cached_ref(
            self,
            "_cached_receipt_ref",
            lambda: "semantic-job-receipt:" + canonical_sha256(self.identity_payload()),
        )
    )


def _journal_path(context: Any) -> Path | None:
    root = context.closure_activation_checkpoint_root
    if root is None:
        return None
    return root / f"handoff-events-{context.build_key_sha256}.bin"


def _journal_event_digest(
    *,
    sequence_no: int,
    artifact_kind: str,
    artifact_ref: str,
    prior_digest: str,
) -> str:
    return canonical_sha256(
        {
            "schema_version": JOURNAL_SCHEMA_VERSION,
            "sequence_no": sequence_no,
            "artifact_kind": artifact_kind,
            "artifact_ref": artifact_ref,
            "prior_digest": prior_digest,
        }
    )


def _prepare_fresh_journal(context: Any) -> None:
    activation = context.closure_activation
    if activation.get("journal_initialized"):
        return
    path = _journal_path(context)
    if path is not None and path.exists():
        # No accepted v3 checkpoint owns this tail. It may be from an interrupted
        # attempt or an incompatible v2 run, so retaining it would make the next
        # sequence non-canonical. Replay artifacts themselves remain immutable.
        path.unlink()
    activation["journal_initialized"] = True


def _append_journal_event(
    context: Any,
    *,
    artifact_kind: str,
    artifact_ref: str,
) -> None:
    if context.reconstructing_owner:
        return
    activation = context.closure_activation
    _prepare_fresh_journal(context)
    sequence_no = int(activation.get("journal_event_count") or 0)
    prior_digest = str(activation.get("journal_digest") or "")
    event_digest = _journal_event_digest(
        sequence_no=sequence_no,
        artifact_kind=artifact_kind,
        artifact_ref=artifact_ref,
        prior_digest=prior_digest,
    )
    try:
        kind_code = _JOURNAL_KIND_CODES[artifact_kind]
    except KeyError as error:
        raise ValueError(
            f"unsupported closure journal event: {artifact_kind}"
        ) from error
    artifact_ref_bytes = artifact_ref.encode("utf-8")
    if not artifact_ref_bytes or len(artifact_ref_bytes) > _JOURNAL_MAX_REF_BYTES:
        raise ValueError("closure journal artifact reference has invalid size")
    prior_digest_bytes = (
        bytes.fromhex(prior_digest) if prior_digest else bytes(_JOURNAL_DIGEST_BYTES)
    )
    event_digest_bytes = bytes.fromhex(event_digest)
    if (
        len(prior_digest_bytes) != _JOURNAL_DIGEST_BYTES
        or len(event_digest_bytes) != _JOURNAL_DIGEST_BYTES
    ):
        raise ValueError("closure journal digest has invalid size")
    frame = b"".join(
        (
            _JOURNAL_HEADER.pack(
                _JOURNAL_MAGIC,
                sequence_no,
                kind_code,
                len(artifact_ref_bytes),
            ),
            artifact_ref_bytes,
            prior_digest_bytes,
            event_digest_bytes,
        )
    )
    path = _journal_path(context)
    started = monotonic_ns()
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        # One small append replaces O(history) tuple copies plus O(history)
        # checkpoint serialization. flush() matches the previous process-crash
        # durability class; optional fsync is available for stronger durability.
        with path.open("ab") as handle:
            handle.write(frame)
            handle.flush()
            fsync_interval = max(
                0,
                int(os.environ.get("SENSIBLAW_CLOSURE_JOURNAL_FSYNC_INTERVAL", "0")),
            )
            if fsync_interval and (sequence_no + 1) % fsync_interval == 0:
                os.fsync(handle.fileno())
    activation["journal_event_count"] = sequence_no + 1
    activation["journal_digest"] = event_digest
    activation["last_journal_artifact_kind"] = artifact_kind
    activation["last_journal_artifact_ref"] = artifact_ref
    # Replay admission is the serial owner authority. Several canonical owner
    # wrappers call this function while already holding ``context.lock``; taking
    # that non-reentrant lock again would deadlock. Keep telemetry on the same
    # serialized admission path instead of introducing a second lock boundary.
    context.closure_counters["handoff_journal_events"] += 1
    context.closure_counters["handoff_journal_append_ns"] += monotonic_ns() - started


def _read_journal(
    context: Any,
    *,
    event_count: int,
    final_digest: str,
) -> tuple[list[dict[str, str]], int]:
    if event_count == 0:
        if final_digest:
            raise ValueError("empty closure journal has a non-empty digest")
        return [], 0
    path = _journal_path(context)
    if path is None or not path.exists():
        raise ValueError("closure handoff journal is missing")
    events: list[dict[str, str]] = []
    prior_digest = ""
    committed_bytes = 0
    with path.open("rb") as handle:
        while len(events) < event_count:
            header = handle.read(_JOURNAL_HEADER.size)
            if not header:
                break
            if len(header) != _JOURNAL_HEADER.size:
                raise ValueError("closure handoff journal contains a partial header")
            try:
                magic, stored_sequence, kind_code, ref_size = _JOURNAL_HEADER.unpack(
                    header
                )
            except struct.error as error:
                raise ValueError("closure handoff journal header is invalid") from error
            if (
                magic != _JOURNAL_MAGIC
                or ref_size == 0
                or ref_size > _JOURNAL_MAX_REF_BYTES
            ):
                raise ValueError("closure handoff journal frame identity mismatch")
            remainder = handle.read(ref_size + 2 * _JOURNAL_DIGEST_BYTES)
            if len(remainder) != ref_size + 2 * _JOURNAL_DIGEST_BYTES:
                raise ValueError("closure handoff journal contains a partial frame")
            sequence_no = len(events)
            artifact_kind = _JOURNAL_CODE_KINDS.get(kind_code, "")
            try:
                artifact_ref = remainder[:ref_size].decode("utf-8")
            except UnicodeDecodeError as error:
                raise ValueError(
                    "closure handoff journal artifact reference is invalid"
                ) from error
            prior_bytes = remainder[ref_size : ref_size + _JOURNAL_DIGEST_BYTES]
            event_bytes = remainder[ref_size + _JOURNAL_DIGEST_BYTES :]
            stored_prior_digest = (
                "" if prior_bytes == bytes(_JOURNAL_DIGEST_BYTES) else prior_bytes.hex()
            )
            if (
                stored_sequence != sequence_no
                or stored_prior_digest != prior_digest
                or artifact_kind not in _JOURNAL_KIND_CODES
                or not artifact_ref
            ):
                raise ValueError("closure handoff journal identity mismatch")
            expected = _journal_event_digest(
                sequence_no=sequence_no,
                artifact_kind=artifact_kind,
                artifact_ref=artifact_ref,
                prior_digest=prior_digest,
            )
            if event_bytes.hex() != expected:
                raise ValueError("closure handoff journal digest mismatch")
            prior_digest = expected
            events.append(
                {"artifact_kind": artifact_kind, "artifact_ref": artifact_ref}
            )
            committed_bytes = handle.tell()
    if len(events) != event_count or prior_digest != final_digest:
        raise ValueError("closure handoff journal is incomplete")
    return events, committed_bytes


def _discard_uncheckpointed_journal_tail(context: Any, committed_bytes: int) -> None:
    """Drop events written after the last atomic frontier checkpoint.

    Such events have replay artifacts but no matching owner revision/frontier
    snapshot. Recomputing that bounded tail is safer than guessing its state.
    """

    path = _journal_path(context)
    if path is None or not path.exists():
        return
    size = path.stat().st_size
    if size <= committed_bytes:
        return
    with path.open("r+b") as handle:
        handle.truncate(committed_bytes)
        handle.flush()
    with context.lock:
        context.closure_counters["handoff_uncheckpointed_tail_bytes"] += (
            size - committed_bytes
        )


def _compact_checkpoint_payload(context: Any) -> dict[str, Any]:
    from src.policy import parallel_semantic_execution as parallel

    activation = context.closure_activation
    payload: dict[str, Any] = {
        "schema_version": HANDOFF_SCHEMA_VERSION,
        "contract_ref": HANDOFF_CONTRACT,
        **parallel._handoff_identity(context),
        "next_leaf_ordinal": int(activation.get("next_leaf_ordinal") or 0),
        # Activation leaves are separately bounded/checkpointed. These lists are
        # small relative to proposal/receipt replay history and retain existing
        # activation resume semantics.
        "completed_leaf_refs": list(activation.get("completed_leaf_refs") or ()),
        "buffered_leaf_refs": list(activation.get("buffered_leaf_refs") or ()),
        "admitted_leaf_refs": list(activation.get("admitted_leaf_refs") or ()),
        "admitted_batch_refs": list(activation.get("admitted_batch_refs") or ()),
        "recorded_delta_refs": list(activation.get("recorded_delta_refs") or ()),
        # The large cumulative replay history lives in the append-only journal.
        "journal_event_count": int(activation.get("journal_event_count") or 0),
        "journal_digest": str(activation.get("journal_digest") or ""),
        "current_owner_revision": int(activation.get("current_owner_revision") or 0),
        "completed_reduction_key_refs": list(
            activation.get("completed_reduction_key_refs") or ()
        ),
        "unresolved_frontier_refs": list(
            activation.get("unresolved_frontier_refs") or ()
        ),
    }
    payload["checkpoint_ref"] = "closure-handoff:" + canonical_sha256(payload)
    return payload


def _write_compact_checkpoint(context: Any) -> None:
    from src.policy import parallel_semantic_execution as parallel

    path = context.closure_handoff_checkpoint_path
    if path is None or context.reconstructing_owner:
        return
    started = monotonic_ns()
    payload = _compact_checkpoint_payload(context)
    parallel._atomic_write_json(path, payload)
    elapsed = monotonic_ns() - started
    with context.lock:
        context.closure_counters["handoff_compact_checkpoints"] += 1
        context.closure_counters["handoff_compact_checkpoint_ns"] += elapsed
        context.closure_counters["handoff_checkpoint_replay_rows_serialized"] += 0


def _load_compact_checkpoint(self: Any) -> dict[str, Any] | None:
    from src.policy import parallel_semantic_execution as parallel

    path = self.context.closure_handoff_checkpoint_path
    if path is None or not path.exists():
        return None
    payload = parallel._read_json(path)
    if payload is None:
        return None
    checkpoint_ref = payload.pop("checkpoint_ref", None)
    expected_ref = "closure-handoff:" + canonical_sha256(payload)
    payload["checkpoint_ref"] = checkpoint_ref
    if (
        payload.get("schema_version") != HANDOFF_SCHEMA_VERSION
        or payload.get("contract_ref") != HANDOFF_CONTRACT
        or any(
            payload.get(key) != value
            for key, value in parallel._handoff_identity(self.context).items()
        )
        or checkpoint_ref != expected_ref
    ):
        return None

    events, committed_bytes = _read_journal(
        self.context,
        event_count=int(payload.get("journal_event_count") or 0),
        final_digest=str(payload.get("journal_digest") or ""),
    )
    _discard_uncheckpointed_journal_tail(self.context, committed_bytes)
    payload["replay_events"] = events
    payload["delta_artifact_refs"] = [
        event["artifact_ref"]
        for event in events
        if event["artifact_kind"] in {"observation_delta", "observation_delta_batch"}
    ]
    payload["proposal_batch_artifact_refs"] = [
        event["artifact_ref"]
        for event in events
        if event["artifact_kind"] == "proposal_batch"
    ]
    payload["receipt_artifact_refs"] = [
        event["artifact_ref"]
        for event in events
        if event["artifact_kind"] == "solver_receipt"
    ]
    payload["reduction_artifact_refs"] = [
        event["artifact_ref"]
        for event in events
        if event["artifact_kind"] == "dirty_reduction"
    ]
    self.context.closure_activation.update(
        {
            key: tuple(value) if isinstance(value, list) else value
            for key, value in payload.items()
            if key not in parallel._handoff_identity(self.context)
        }
    )
    self.context.closure_activation["journal_initialized"] = True
    return payload


def _install_reconstruction_cleanup(parallel: Any) -> None:
    original_reconstruct = parallel.ClosureOwnerReplayContract.reconstruct

    def reconstruct(self: Any, owner: Any) -> None:
        original_reconstruct(self, owner)
        if not self.available:
            return
        # Replay lists are a one-time reconstruction view. Keeping them after
        # owner reconstruction would recreate the old cumulative-memory cost.
        activation = self.context.closure_activation
        for key in (
            "replay_events",
            "delta_artifact_refs",
            "proposal_batch_artifact_refs",
            "receipt_artifact_refs",
            "reduction_artifact_refs",
        ):
            activation.pop(key, None)

    parallel.ClosureOwnerReplayContract.reconstruct = reconstruct


def install_owner_handoff_performance() -> bool:
    """Install O(new-event) replay bookkeeping without changing semantics."""

    from src.policy import operational_corpus_compilation as operational
    from src.policy import parallel_semantic_execution as parallel

    if getattr(parallel, _INSTALL_MARKER, False):
        return False
    if not getattr(operational, parallel._INSTALL_MARKER, False):
        raise RuntimeError(
            "owner handoff performance must install after parallel semantic execution"
        )

    _install_identity_caches()

    # A v2 checkpoint is intentionally ignored rather than interpreted under a
    # different physical replay contract. Semantic content is recomputed from
    # the immutable source/proposal inputs.
    parallel.CLOSURE_HANDOFF_SCHEMA_VERSION = HANDOFF_SCHEMA_VERSION
    parallel.CLOSURE_HANDOFF_CONTRACT = HANDOFF_CONTRACT
    parallel._append_replay_event = _append_journal_event
    parallel._write_closure_handoff_checkpoint = _write_compact_checkpoint
    parallel.ClosureOwnerReplayContract._load_checkpoint = _load_compact_checkpoint
    _install_reconstruction_cleanup(parallel)

    setattr(parallel, _INSTALL_MARKER, True)
    return True


__all__ = [
    "HANDOFF_CONTRACT",
    "HANDOFF_SCHEMA_VERSION",
    "JOURNAL_SCHEMA_VERSION",
    "install_owner_handoff_performance",
]
