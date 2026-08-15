from __future__ import annotations

from typing import Any, Iterator, Mapping

import pytest

from src.policy import artifact_projection
from src.policy import carrier_orchestration_hot_path as hot


def _sealed_example() -> tuple[dict[str, Any], Any]:
    projector = hot._seal_projected_reader(artifact_projection.project_artifacts)
    projected, reader = projector(
        {
            "pnf_graph": {
                "graph_ref": "graph:test",
                "factors": ({"factor_ref": "factor:1", "factor_type": "norm"},),
            }
        },
        policy=artifact_projection.ArtifactProjectionPolicy.production(),
    )
    return projected["pnf_graph"], reader


def test_matching_producer_seal_skips_second_digest_pass() -> None:
    descriptor, reader = _sealed_example()

    def fallback(*_args: Any, **_kwargs: Any) -> Iterator[tuple[Mapping[str, Any], ...]]:
        raise AssertionError("full verifier should not run for matching producer seal")
        yield ()

    verifier = hot._sealed_iter_verified_records(fallback)
    rows = [row for batch in verifier(reader, descriptor, batch_size=1) for row in batch]

    assert len(rows) == descriptor["record_count"]


def test_changed_descriptor_digest_falls_back_to_full_verifier() -> None:
    descriptor, reader = _sealed_example()
    changed = {**descriptor, "ordered_digest": "0" * 64}
    called = False

    def fallback(*_args: Any, **_kwargs: Any) -> Iterator[tuple[Mapping[str, Any], ...]]:
        nonlocal called
        called = True
        yield ()

    verifier = hot._sealed_iter_verified_records(fallback)
    list(verifier(reader, changed))

    assert called is True


def test_seal_fast_path_still_rejects_record_count_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    descriptor, reader = _sealed_example()
    original = reader.iter_records

    def short_reader(artifact_key: str, batch_size: int = 256):
        batches = list(original(artifact_key, batch_size))
        for batch in batches[:-1]:
            yield batch

    monkeypatch.setattr(reader, "iter_records", short_reader)
    verifier = hot._sealed_iter_verified_records(artifact_projection.iter_verified_records)

    with pytest.raises(ValueError, match="record count mismatch"):
        list(verifier(reader, descriptor))


def test_seal_disable_restores_full_verification(monkeypatch: pytest.MonkeyPatch) -> None:
    descriptor, reader = _sealed_example()
    monkeypatch.setenv("SENSIBLAW_TRUST_INPROCESS_ARTIFACT_SEALS", "0")
    called = False

    def fallback(*_args: Any, **_kwargs: Any) -> Iterator[tuple[Mapping[str, Any], ...]]:
        nonlocal called
        called = True
        yield ()

    list(hot._sealed_iter_verified_records(fallback)(reader, descriptor))
    assert called is True


def test_receipt_only_verify_uses_matching_producer_seal() -> None:
    descriptor, reader = _sealed_example()

    def fallback(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("receipt-only verifier should use producer seal")

    hot._sealed_receipt_verify(fallback)(reader, descriptor)


def test_manifest_telemetry_hot_path_does_not_json_size_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reader = artifact_projection.InMemoryArtifactManifestReader(
        {"rows": tuple(range(9))}
    )

    class Ledger:
        def __init__(self) -> None:
            self.rows: list[int] = []

        def batch(
            self,
            _stage: str,
            *,
            rows: int,
            payload_bytes: int = 0,
            **_kwargs: Any,
        ) -> None:
            assert payload_bytes == 0
            self.rows.append(rows)

    ledger = Ledger()
    reader._resource_ledger = ledger
    monkeypatch.setenv("SENSIBLAW_MANIFEST_TELEMETRY_STRIDE", "2")
    monkeypatch.setattr(
        artifact_projection.json,
        "dumps",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("telemetry must not JSON-serialise records")
        ),
    )
    original = hot._install_manifest_replay_hot_path()
    try:
        rows = [row for batch in reader.iter_records("rows", 2) for row in batch]
    finally:
        artifact_projection.InMemoryArtifactManifestReader.iter_records = original

    assert len(rows) == 9
    assert sum(ledger.rows) == 9


def test_resource_sampler_reads_smaps_rollup_once(monkeypatch: pytest.MonkeyPatch) -> None:
    reads = 0

    def read_text(_self: Any, **_kwargs: Any) -> str:
        nonlocal reads
        reads += 1
        return "Pss: 10 kB\nPrivate_Clean: 3 kB\nPrivate_Dirty: 4 kB\n"

    monkeypatch.setattr(hot.Path, "read_text", read_text)
    monkeypatch.setattr(hot.execution_resource_ledger, "_rss_bytes", lambda: 20 * 1024)

    result = hot._single_read_process_resources()

    assert reads == 1
    assert result["pss_bytes"] == 10 * 1024
    assert result["uss_bytes"] == 7 * 1024


def test_factor_revision_memo_hashes_same_mapping_once() -> None:
    calls = 0

    def original(factor: Mapping[str, Any]) -> str:
        nonlocal calls
        calls += 1
        return f"revision:{factor['factor_ref']}:{factor['closure_state']}"

    memoized = hot._memoized_factor_revision_ref(original)
    factor = {"factor_ref": "factor:1", "closure_state": "closed"}

    first = memoized(factor)
    second = memoized(factor)

    assert first == second
    assert calls == 1


def test_factor_revision_memo_does_not_alias_equal_distinct_mappings() -> None:
    calls = 0

    def original(factor: Mapping[str, Any]) -> str:
        nonlocal calls
        calls += 1
        return f"revision:{factor['factor_ref']}:{calls}"

    memoized = hot._memoized_factor_revision_ref(original)
    left = {"factor_ref": "factor:1"}
    right = {"factor_ref": "factor:1"}

    assert memoized(left) != memoized(right)
    assert calls == 2
