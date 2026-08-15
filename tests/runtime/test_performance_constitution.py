from __future__ import annotations

from src.runtime.performance_constitution import assess_replay_run, assess_reuse_pair


def _state(result: dict[str, object], requirement_ref: str) -> str:
    rows = result["requirements"]
    assert isinstance(rows, list)
    for row in rows:
        assert isinstance(row, dict)
        if row["requirement_ref"] == requirement_ref:
            return str(row["state"])
    raise AssertionError(requirement_ref)


def test_single_run_does_not_invent_missing_parser_ratio() -> None:
    result = assess_replay_run(
        {
            "completed": True,
            "parity": {"semantic_parity": True},
            "kernel_seconds": {"local_typing": 1.0, "closure": 2.0},
        }
    )

    assert result["hard_gate"] == "pass"
    assert _state(result, "post_parser_to_spacy_ratio") == "unknown"
    assert "incremental_economy" in result["claims_not_established_by_single_run"]


def test_explicit_parser_ratio_enforces_ten_percent_target() -> None:
    passing = assess_replay_run(
        {
            "completed": True,
            "parity": {"semantic_parity": True},
            "kernel_seconds": {"spacy_parser": 10.0, "post_parser": 1.0},
        }
    )
    failing = assess_replay_run(
        {
            "completed": True,
            "parity": {"semantic_parity": True},
            "kernel_seconds": {"spacy_parser": 10.0, "post_parser": 1.01},
        }
    )

    assert _state(passing, "post_parser_to_spacy_ratio") == "pass"
    assert _state(failing, "post_parser_to_spacy_ratio") == "fail"


def test_semantic_parity_is_a_hard_gate() -> None:
    result = assess_replay_run(
        {"completed": True, "parity": {"semantic_parity": False}}
    )

    assert result["hard_gate"] == "fail"


def test_reuse_non_increase_requires_exact_controlled_identity() -> None:
    before = {
        "workload_ref": "workload:1",
        "configuration_ref": "config:1",
        "semantic_work_units": 100,
    }
    after = {
        "workload_ref": "workload:1",
        "configuration_ref": "config:1",
        "semantic_work_units": 80,
    }

    assert assess_reuse_pair(before, after)["state"] == "pass"
    assert assess_reuse_pair(before, {**after, "configuration_ref": "config:2"})[
        "state"
    ] == "unknown"


def test_reuse_regression_fails_controlled_economy_contract() -> None:
    before = {
        "workload_ref": "workload:1",
        "configuration_ref": "config:1",
        "semantic_work_units": 100,
    }
    after = {**before, "semantic_work_units": 101}

    assert assess_reuse_pair(before, after)["state"] == "fail"
