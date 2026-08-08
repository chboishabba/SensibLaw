from __future__ import annotations

import json

import pytest

from src.policy.ordered_world_parser_lookahead import (
    ORDERED_WORLD_LOOKAHEAD_CONTRACT,
    ParserLookaheadAllocation,
    allocate_parser_lookahead,
    compile_directory_postgres_ordered_world,
)
from src.policy.ordered_world_parser_lookahead import _completed_document_refs


def test_parser_lookahead_reserves_matching_parser_lane() -> None:
    allocation = allocate_parser_lookahead(
        global_worker_budget=4,
        parser_workers=2,
    )

    assert allocation.enabled is True
    assert allocation.parser_lookahead_workers == 2
    assert allocation.foreground_worker_budget == 2
    assert (
        allocation.foreground_worker_budget
        + allocation.parser_lookahead_workers
        == allocation.global_worker_budget
    )


def test_parser_lookahead_disables_when_identity_preserving_split_is_impossible() -> None:
    allocation = allocate_parser_lookahead(
        global_worker_budget=3,
        parser_workers=2,
    )

    assert allocation.enabled is False
    assert allocation.parser_lookahead_workers == 0
    assert allocation.foreground_worker_budget == 3
    assert "required=4" in allocation.reason


def test_allocation_rejects_global_oversubscription() -> None:
    with pytest.raises(ValueError, match="exceed the global worker budget"):
        ParserLookaheadAllocation(
            global_worker_budget=4,
            foreground_worker_budget=3,
            parser_lookahead_workers=2,
            enabled=True,
            reason="invalid",
        )


def test_completed_document_refs_admit_only_published_states(tmp_path) -> None:
    state_path = tmp_path / "compile.json"
    state_path.write_text(
        json.dumps(
            {
                "documents": {
                    "document:1": {"state": "compiled"},
                    "document:2": {"state": "reused_compilation"},
                    "document:3": {"state": "running"},
                    "document:4": {"state": "failed"},
                }
            }
        ),
        encoding="utf-8",
    )

    assert _completed_document_refs(state_path) == {"document:1", "document:2"}


def test_ordered_world_rejects_parallel_semantic_documents() -> None:
    with pytest.raises(ValueError, match="document_workers=1"):
        compile_directory_postgres_ordered_world(
            ".",
            document_workers=2,
        )


def test_contract_names_parser_authority_only() -> None:
    assert ORDERED_WORLD_LOOKAHEAD_CONTRACT == "ordered-world-parser-lookahead:v0_1"
