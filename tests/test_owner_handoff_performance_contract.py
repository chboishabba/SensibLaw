from __future__ import annotations

from collections import Counter
from pathlib import Path
from threading import Lock

from src.policy.owner_handoff_performance import (
    HANDOFF_CONTRACT,
    HANDOFF_SCHEMA_VERSION,
    _append_journal_event,
    _discard_uncheckpointed_journal_tail,
    _journal_path,
    _read_journal,
)


class _Context:
    def __init__(self, root: Path) -> None:
        self.closure_activation_checkpoint_root = root
        self.build_key_sha256 = "build-key"
        self.reconstructing_owner = False
        self.closure_activation: dict[str, object] = {}
        self.closure_counters: Counter[str] = Counter()
        self.lock = Lock()


def test_handoff_contract_is_new_compatibility_identity() -> None:
    assert HANDOFF_SCHEMA_VERSION == "sensiblaw.closure-handoff-state.v3"
    assert HANDOFF_CONTRACT == "closure-owner-replay:v3"


def test_journal_append_is_incremental_and_does_not_retain_full_history(
    tmp_path: Path,
) -> None:
    context = _Context(tmp_path)
    for ordinal in range(256):
        _append_journal_event(
            context,
            artifact_kind="proposal_batch",
            artifact_ref=f"artifact:{ordinal}",
        )

    assert context.closure_activation["journal_event_count"] == 256
    assert "replay_events" not in context.closure_activation
    assert "proposal_batch_artifact_refs" not in context.closure_activation
    assert context.closure_counters["handoff_journal_events"] == 256

    path = _journal_path(context)
    assert path is not None
    assert path.exists()
    assert len(path.read_text(encoding="utf-8").splitlines()) == 256


def test_journal_digest_chain_round_trips_exact_checkpoint_prefix(
    tmp_path: Path,
) -> None:
    context = _Context(tmp_path)
    for ordinal in range(12):
        _append_journal_event(
            context,
            artifact_kind="dirty_reduction",
            artifact_ref=f"reduction:{ordinal}",
        )

    events, committed_bytes = _read_journal(
        context,
        event_count=12,
        final_digest=str(context.closure_activation["journal_digest"]),
    )
    assert [row["artifact_ref"] for row in events] == [
        f"reduction:{ordinal}" for ordinal in range(12)
    ]
    assert committed_bytes == _journal_path(context).stat().st_size  # type: ignore[union-attr]


def test_uncheckpointed_tail_is_dropped_before_replay_continues(
    tmp_path: Path,
) -> None:
    context = _Context(tmp_path)
    for ordinal in range(4):
        _append_journal_event(
            context,
            artifact_kind="proposal_batch",
            artifact_ref=f"proposal:{ordinal}",
        )

    checkpoint_digest = str(context.closure_activation["journal_digest"])
    events, committed_bytes = _read_journal(
        context,
        event_count=4,
        final_digest=checkpoint_digest,
    )
    assert len(events) == 4

    # Simulate a process dying after writing the next event artifact/journal row
    # but before the atomic owner-frontier checkpoint was replaced.
    _append_journal_event(
        context,
        artifact_kind="proposal_batch",
        artifact_ref="proposal:uncheckpointed",
    )
    path = _journal_path(context)
    assert path is not None
    assert path.stat().st_size > committed_bytes

    _discard_uncheckpointed_journal_tail(context, committed_bytes)
    assert path.stat().st_size == committed_bytes


def test_source_contract_removes_quadratic_replay_event_tuple_copy() -> None:
    source = Path("src/policy/owner_handoff_performance.py").read_text(
        encoding="utf-8"
    )
    legacy = Path("src/policy/parallel_semantic_execution.py").read_text(
        encoding="utf-8"
    )
    policy_init = Path("src/policy/__init__.py").read_text(encoding="utf-8")

    assert 'events = list(activation.get("replay_events") or ())' in legacy
    assert 'refs = list(activation.get(list_key) or ())' in legacy
    assert "parallel._append_replay_event = _append_journal_event" in source
    assert "parallel._write_closure_handoff_checkpoint = _write_compact_checkpoint" in source
    assert "install_owner_handoff_performance()" in policy_init


def test_source_contract_removes_duplicate_recorded_delta_index() -> None:
    legacy = Path("src/policy/parallel_semantic_execution.py").read_text(
        encoding="utf-8"
    )
    bounded = Path("src/policy/bounded_operational_execution.py").read_text(
        encoding="utf-8"
    )
    batch = Path("src/policy/owner_handoff_batch_performance.py").read_text(
        encoding="utf-8"
    )
    policy_init = Path("src/policy/__init__.py").read_text(encoding="utf-8")

    assert 'if delta.delta_ref not in owner._observation_deltas' in bounded
    assert 'set(self.context.closure_activation.get("recorded_delta_refs") or ())' in legacy
    assert "new_deltas = tuple(deltas)" in batch
    assert 'payload.pop("recorded_delta_refs", None)' in batch
    assert "install_owner_handoff_batch_performance()" in policy_init
    assert "current closure handoff checkpoint identity mismatch" in batch
