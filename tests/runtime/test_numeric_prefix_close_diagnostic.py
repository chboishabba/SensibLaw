from __future__ import annotations

import json
import importlib.util
from pathlib import Path

import pytest

from src.runtime.numeric_prefix_close_diagnostic import (
    PREFIX_CLOSE_DIAGNOSTIC_REF,
    STOP_AFTER_ENV,
    STOP_OUTPUT_ENV,
    prefix_close_diagnostic_config,
    record_prefix_close_completion,
)


def test_prefix_close_diagnostic_is_off_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(STOP_AFTER_ENV, raising=False)
    monkeypatch.delenv(STOP_OUTPUT_ENV, raising=False)

    assert prefix_close_diagnostic_config() is None


def test_prefix_close_diagnostic_requires_positive_stop_and_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(STOP_AFTER_ENV, "0")
    monkeypatch.setenv(STOP_OUTPUT_ENV, str(tmp_path / "prefix.jsonl"))
    with pytest.raises(ValueError, match="must be positive"):
        prefix_close_diagnostic_config()

    monkeypatch.setenv(STOP_AFTER_ENV, "32")
    monkeypatch.delenv(STOP_OUTPUT_ENV, raising=False)
    with pytest.raises(ValueError, match="is required"):
        prefix_close_diagnostic_config()


def test_prefix_completion_receipt_is_written_only_at_committed_boundary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output = tmp_path / "prefix.jsonl"
    monkeypatch.setenv(STOP_AFTER_ENV, "32")
    monkeypatch.setenv(STOP_OUTPUT_ENV, str(output))
    config = prefix_close_diagnostic_config()
    assert config is not None

    with pytest.raises(ValueError, match="before its stop boundary"):
        record_prefix_close_completion(
            config,
            run_ref="run",
            worker_ref="worker",
            committed_sentence_closes=31,
            work_id=7,
            region_id=11,
            released_unstarted_leases=4,
        )
    assert not output.exists()

    record_prefix_close_completion(
        config,
        run_ref="run",
        worker_ref="worker",
        committed_sentence_closes=32,
        work_id=7,
        region_id=11,
        released_unstarted_leases=4,
    )
    record = json.loads(output.read_text().splitlines()[0])
    assert record["contract_ref"] == PREFIX_CLOSE_DIAGNOSTIC_REF
    assert record["committed_sentence_closes"] == 32
    assert record["last_committed_work_id"] == 7
    assert record["last_committed_region_id"] == 11
    assert record["released_unstarted_leases"] == 4
    assert "committed normally" in record["semantic_state"]


def test_bounded_sentence_leasing_places_stop_after_transaction_commit() -> None:
    source = Path("src/policy/bounded_sentence_batch_leasing.py").read_text()

    transaction = "with connection.transaction():"
    committed_branch = "else:\n                        # Reaching this branch means"
    receipt = "record_prefix_close_completion("
    signal = "raise NumericPrefixDiagnosticComplete("
    release = "release_unstarted_leases(cursor, remaining)"

    assert transaction in source
    assert committed_branch in source
    assert source.index(committed_branch) < source.index(
        release, source.index(committed_branch)
    )
    assert source.index(release, source.index(committed_branch)) < source.index(receipt)
    assert source.index(receipt) < source.index(signal)
    assert "isinstance(error, NumericPrefixDiagnosticComplete)" in source


def test_prefix_runner_allows_an_undistorted_profile_without_explain() -> None:
    script = Path("scripts/run_numeric_prefix_close_diagnostic.py")
    spec = importlib.util.spec_from_file_location("prefix_runner", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module._paired_request(None, None, label="--explain") is None
    with pytest.raises(ValueError, match="supplied together"):
        module._paired_request("128", None, label="--explain")


def test_prefix_runner_rejects_missing_or_duplicate_close_explain_ordinals(
    tmp_path: Path,
) -> None:
    script = Path("scripts/run_numeric_prefix_close_diagnostic.py")
    spec = importlib.util.spec_from_file_location("prefix_runner", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    receipt = tmp_path / "close.jsonl"
    receipt.write_text(
        "\n".join(
            json.dumps({"selection": {"close_ordinal": value}})
            for value in (512, 512, 1024)
        )
        + "\n"
    )

    assert module._observed_close_explain_ordinals(receipt) == (512, 512, 1024)
