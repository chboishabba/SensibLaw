from __future__ import annotations

from src import zelph_bridge


def test_required_output_contract_distinguishes_no_match(monkeypatch) -> None:
    monkeypatch.setattr(zelph_bridge, "parse_zelph_inference", lambda _output: [])

    class _Result:
        stdout = ""
        stderr = ""

    monkeypatch.setattr(zelph_bridge.subprocess, "run", lambda *args, **kwargs: _Result())
    receipt = zelph_bridge.run_zelph_inference(
        "facts", "rules", required_output_predicates=("au_procedural_fact",)
    )

    assert receipt["execution_outcome"] == "failed_required_output_contract"
    assert receipt["handoff_success"] is False
    assert receipt["missing_required_output_predicates"] == ["au_procedural_fact"]


def test_execution_receipt_marks_emitted_required_output(monkeypatch) -> None:
    triples = [{"subject": "fact:one", "predicate": "au_procedural_fact", "object": "true"}]
    monkeypatch.setattr(zelph_bridge, "parse_zelph_inference", lambda _output: triples)

    class _Result:
        stdout = "output"
        stderr = ""

    monkeypatch.setattr(zelph_bridge.subprocess, "run", lambda *args, **kwargs: _Result())
    receipt = zelph_bridge.run_zelph_inference(
        "facts", "rules", required_output_predicates=("au_procedural_fact",)
    )

    assert receipt["execution_outcome"] == "executed_with_output"
    assert receipt["handoff_success"] is True
