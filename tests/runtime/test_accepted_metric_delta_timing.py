from __future__ import annotations

from src.runtime.accepted_metric_ledger import build_accepted_metric_ledger


def _run() -> dict[str, object]:
    return {
        "numeric_work_timing": {
            "source_ref": "parser-source:test",
            "token_count": 2522,
            "sentence_count": 95,
            "pnf_sentence_adjacent_pairs": 94,
            "pnf_paragraph_adjacent_pairs": 7,
            "pnf_visible_index_rows": 321,
            "spacy_parser_wall_occupancy_ns": 414_000_000,
            "post_parser_wall_occupancy_ns": 4_567_000_000,
            "parser_post_overlap_ns": 0,
            "spacy_parser_only_wall_ns": 414_000_000,
            "post_parser_only_wall_ns": 4_567_000_000,
            "timing_basis": "process-active-work+monotonic-wall-occupancy:v3",
            "numeric_projection_worker_work_ns": 120_000_000,
            "sentence_closure_worker_work_ns": 715_000_000,
            "sentence_closure_coordinator_ns": 391_000_000,
            "sentence_adjacency_ns": 354_000_000,
            "hierarchy_work_ns": 800_000_000,
            "paragraph_adjacency_ns": 100_000_000,
            "lookup_publication_ns": 50_000_000,
            "summary_work_ns": 25_000_000,
            "post_parser_coordinator_ns": 1_720_000_000,
            "unclassified_orchestration_wall_ns": 210_000_000,
        }
    }


def test_native_delta_timing_is_off_by_default(monkeypatch) -> None:
    monkeypatch.delenv("SENSIBLAW_NATIVE_DELTA_TIMING", raising=False)
    ledger = build_accepted_metric_ledger(_run()).to_dict()
    delta = ledger["delta_execution_timing"]
    assert delta["enabled"] is False
    assert delta["observations"] == []


def test_native_delta_timing_attributes_direct_stage_measurements(monkeypatch) -> None:
    monkeypatch.setenv("SENSIBLAW_NATIVE_DELTA_TIMING", "1")
    ledger = build_accepted_metric_ledger(_run()).to_dict()
    delta = ledger["delta_execution_timing"]

    assert delta["enabled"] is True
    assert delta["semantic_authority_effect"] == "none"
    assert delta["semantic_identity_effect"] == "none"
    assert delta["owner_totals_ns"] == {
        "numeric_projection_worker": 120_000_000,
        "sentence_closure_worker": 715_000_000,
        "sentence_closure_coordinator": 391_000_000,
        "sentence_adjacency": 354_000_000,
        "hierarchy_materialization": 800_000_000,
        "paragraph_adjacency": 100_000_000,
        "global_lookup_publication": 50_000_000,
    }
    assert delta["stage_totals_ns"] == {
        "source_delta": 0,
        "projection_atoms": 120_000_000,
        "affected_keys": 0,
        "local_reducer": 2_360_000_000,
        "authority_publication": 50_000_000,
    }


def test_unclassified_and_summary_work_are_not_fake_delta_owners(monkeypatch) -> None:
    monkeypatch.setenv("SENSIBLAW_NATIVE_DELTA_TIMING", "1")
    delta = build_accepted_metric_ledger(_run()).to_dict()["delta_execution_timing"]
    owners = delta["owner_totals_ns"]
    assert "unclassified_orchestration" not in owners
    assert "summary_work" not in owners


def test_parser_relative_gate_still_uses_direct_occupancy(monkeypatch) -> None:
    monkeypatch.setenv("SENSIBLAW_NATIVE_DELTA_TIMING", "1")
    ledger = build_accepted_metric_ledger(_run())
    assert ledger.parser_relative_ratio == 4_567_000_000 / 414_000_000
    assert ledger.delta_execution_timing.enabled is True
