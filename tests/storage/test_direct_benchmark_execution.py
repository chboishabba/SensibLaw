from __future__ import annotations

from dataclasses import dataclass

import pytest

import src.storage.postgres.direct_benchmark_execution as direct
from src.storage.postgres.semantic_execution_mode import SemanticExecutionMode
from src.storage.postgres.spacy_parser_model import ParserExecutionSummary


class _Cursor:
    def __init__(self, row):
        self.row = row
        self.query = ""
        self.params = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def execute(self, query, params=None):
        self.query = str(query)
        self.params = params

    def fetchone(self):
        return self.row


class _Connection:
    def __init__(self, row):
        self.cursor_value = _Cursor(row)

    def cursor(self):
        return self.cursor_value

    def close(self):
        pass


def test_zero_projection_receipt_requires_zero_parser_rows(monkeypatch) -> None:
    connection = _Connection((0, 0, 0, 7, 100))
    monkeypatch.setattr(direct, "connect", lambda _url: connection)
    receipt = direct._direct_zero_projection_receipt(
        "postgresql://unused", run_ref="run", document_ref="doc"
    )
    assert receipt == {
        "parser_sentence_writes": 0,
        "parser_token_writes": 0,
        "parser_entity_writes": 0,
        "stable_evidence_rows": 7,
        "spacy_observed_ns": 100,
    }
    assert "semantic_parser_token" in connection.cursor_value.query
    assert connection.cursor_value.params == ("run", "doc") * 5


def test_zero_projection_receipt_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(direct, "connect", lambda _url: _Connection((0, 1, 0, 7, 100)))
    with pytest.raises(RuntimeError, match="zero parser projection"):
        direct._direct_zero_projection_receipt(
            "postgresql://unused", run_ref="run", document_ref="doc"
        )


@dataclass
class _Compatibility:
    summary: ParserExecutionSummary

    def __getitem__(self, key):
        if key == "parser_receipt":
            return {"legacy_return_surface": True}
        raise KeyError(key)


def test_benchmark_entrypoint_forces_direct_and_returns_evidence_carrier(monkeypatch) -> None:
    summary = ParserExecutionSummary(
        run_ref="run",
        document_ref="doc",
        source_ref="source",
        parser_contract_ref="contract",
        coverage_state="complete",
        sentence_count=2,
        token_count=5,
        partition_count=1,
        entity_count=0,
        boundary_obligation_count=0,
    )
    observed = {}

    def fake_run(**kwargs):
        observed.update(kwargs)
        return _Compatibility(summary)

    monkeypatch.setattr(direct, "run_streaming_spacy_execution", fake_run)
    monkeypatch.setattr(direct, "direct_execution_summary", lambda *args, **kwargs: summary)
    monkeypatch.setattr(
        direct,
        "_direct_zero_projection_receipt",
        lambda *args, **kwargs: {
            "parser_sentence_writes": 0,
            "parser_token_writes": 0,
            "parser_entity_writes": 0,
            "stable_evidence_rows": 5,
            "spacy_observed_ns": 100,
        },
    )
    ticks = iter((1000, 1150))
    monkeypatch.setattr(direct, "monotonic_ns", lambda: next(ticks))

    carrier = direct.run_direct_benchmark_execution(
        database_url="postgresql://unused",
        run_ref="run",
        document_ref="doc",
        canonical_text="Alpha beta.",
        parser_contract_ref="contract",
        artifact_root="/tmp/artifacts",
        worker_count=1,
    )

    assert observed["semantic_execution_mode"] is SemanticExecutionMode.DIRECT
    assert carrier.summary == summary
    receipt = carrier["parser_receipt"]
    assert receipt["parser_token_writes"] == 0
    assert receipt["gate_a_benchmark_ready"] is True
    assert receipt["authority"] == "stable_source_evidence_and_direct_pnf_hyperfabric"
    assert receipt["optimized_direct_total_ns"] == 150
    assert receipt["direct_over_spacy_ratio"] == 1.5
    assert receipt["agda_first_stage_target_met"] is True
