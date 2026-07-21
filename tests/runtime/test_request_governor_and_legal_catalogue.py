from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.runtime.request_governor import RequestGovernor, RequestGovernorPolicy


ROOT = Path(__file__).resolve().parents[2]


def test_request_governor_enforces_budget_and_records_attempts() -> None:
    now = [0.0]
    sleeps: list[float] = []

    def clock() -> float:
        return now[0]

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        now[0] += seconds

    governor = RequestGovernor(
        RequestGovernorPolicy(
            minimum_interval_seconds=2.0,
            maximum_attempts=1,
            backoff_seconds=0,
            jitter_seconds=0,
            request_budget=2,
        ),
        clock=clock,
        sleeper=sleep,
        random_value=lambda: 0.0,
    )

    assert governor.call("https://www.austlii.edu.au/a", lambda: "a") == "a"
    assert governor.call("https://www.austlii.edu.au/b", lambda: "b") == "b"
    assert sleeps == [2.0]
    assert governor.request_count == 2
    assert [row.state for row in governor.receipts] == ["completed", "completed"]

    with pytest.raises(RuntimeError, match="budget exhausted"):
        governor.call("https://www.austlii.edu.au/c", lambda: "c")


def test_au_driving_catalogue_is_bounded_and_preserves_existing_tranche() -> None:
    path = ROOT / "config/legal_catalogues/au_driving_austlii_v1.json"
    catalogue = json.loads(path.read_text(encoding="utf-8"))

    assert catalogue["provider"]["endpoint_ref"] == "au:austlii"
    assert catalogue["provider"]["authority_level"] == "supporting"
    assert set(catalogue["request_policy"]["allowed_hosts"]) == {
        "www.austlii.edu.au",
        "austlii.edu.au",
    }
    assert 0 < catalogue["request_policy"]["request_budget"] <= 100
    assert {row["jurisdiction"] for row in catalogue["search_terms"]} == {
        "AU",
        "AU.QLD",
    }
    assert {
        row["path"] for row in catalogue["persisted_source_families"]
    } == {
        "demo/ingest/legal_principles_au_v1",
        "demo/ingest/hca_case_s942025",
    }
    assert all(row["max_file_bytes"] == 10_000_000 for row in catalogue["persisted_source_families"])
