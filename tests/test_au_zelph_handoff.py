from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import build_au_zelph_handoff as handoff
from src.storage.postgres.follow_projection_store import FollowProjectionQueryResult


def _query_result() -> FollowProjectionQueryResult:
    return FollowProjectionQueryResult(
        projection={
            "projection_ref": "follow-projection:au",
            "document_ref": "document:au",
            "profile_ref": "profile:au",
            "scope_ref": "document:au",
            "projection_kind": "legal",
            "derived_only": True,
            "challengeable": True,
            "promotes_truth": False,
            "execution_authority": False,
        },
        nodes=(
            {
                "node_ref": "node:fact",
                "node_kind": "semantic.procedural_outcome",
                "label": "Procedural outcome",
            },
        ),
        edges=(),
        evidence=(),
        provenance=(),
        admissibility_grounds=(),
    )


class _Cursor:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _Connection:
    def cursor(self):
        return _Cursor()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_au_zelph_handoff_requires_procedural_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(handoff, "_connect", lambda _url: _Connection())
    monkeypatch.setattr(
        handoff,
        "query_follow_projection",
        lambda _cursor, _ref: _query_result(),
    )
    monkeypatch.setattr(
        handoff,
        "run_zelph_inference",
        lambda _facts, _rules: {
            "status": "ok",
            "results": [
                {
                    "predicate": "au_procedural_fact",
                    "triple_ref": "triple:1",
                }
            ],
        },
    )
    payload = handoff.build_handoff_artifact(
        database_url="postgresql://example/test",
        projection_ref="follow-projection:au",
        output_dir=tmp_path,
    )
    assert payload["successful_handoff"] is True
    assert payload["execution"]["outcome"] == "executed_with_output"
    assert json.loads(Path(payload["receipt_path"]).read_text())["successful_handoff"] is True
    assert json.loads(Path(payload["presentation_path"]).read_text())["semantic_input_allowed"] is False


def test_au_zelph_handoff_fails_when_required_predicate_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(handoff, "_connect", lambda _url: _Connection())
    monkeypatch.setattr(
        handoff,
        "query_follow_projection",
        lambda _cursor, _ref: _query_result(),
    )
    monkeypatch.setattr(
        handoff,
        "run_zelph_inference",
        lambda _facts, _rules: {
            "status": "ok",
            "results": [{"predicate": "other", "triple_ref": "triple:2"}],
        },
    )
    payload = handoff.build_handoff_artifact(
        database_url="postgresql://example/test",
        projection_ref="follow-projection:au",
        output_dir=tmp_path,
    )
    assert payload["successful_handoff"] is False
    assert payload["execution"]["outcome"] == "failed_required_output"
