from __future__ import annotations

import pytest

from src.storage.postgres.semantic_execution_mode import (
    SemanticExecutionMode,
    SemanticParityError,
    parse_semantic_execution_mode,
    route_semantic_observation,
)


def test_parse_semantic_execution_mode_is_strict() -> None:
    assert parse_semantic_execution_mode("DIRECT") is SemanticExecutionMode.DIRECT
    assert parse_semantic_execution_mode(" reference ") is SemanticExecutionMode.REFERENCE
    assert parse_semantic_execution_mode("parity") is SemanticExecutionMode.PARITY
    with pytest.raises(ValueError, match="direct, reference, parity"):
        parse_semantic_execution_mode("shadow")


def test_direct_does_not_evaluate_reference() -> None:
    calls: list[str] = []
    routed = route_semantic_observation(
        "direct",
        direct=lambda: calls.append("direct") or (b"object", b"factor"),
        reference=lambda: calls.append("reference") or (),
    )
    assert calls == ["direct"]
    assert routed.selected == (b"object", b"factor")
    assert routed.reference is None


def test_reference_does_not_evaluate_direct() -> None:
    calls: list[str] = []
    routed = route_semantic_observation(
        "reference",
        direct=lambda: calls.append("direct") or (),
        reference=lambda: calls.append("reference") or (b"reference",),
    )
    assert calls == ["reference"]
    assert routed.selected == (b"reference",)
    assert routed.direct is None


def test_parity_returns_only_after_both_observations_match() -> None:
    calls: list[str] = []
    observation = (b"object", b"factor", b"demand")
    routed = route_semantic_observation(
        "parity",
        direct=lambda: calls.append("direct") or observation,
        reference=lambda: calls.append("reference") or observation,
    )
    assert calls == ["direct", "reference"]
    assert routed.selected == observation
    assert routed.direct == routed.reference == observation


def test_parity_mismatch_fails_closed_without_selected_observation() -> None:
    calls: list[str] = []
    with pytest.raises(SemanticParityError, match="publication aborted"):
        route_semantic_observation(
            "parity",
            direct=lambda: calls.append("direct") or (b"direct",),
            reference=lambda: calls.append("reference") or (b"reference",),
        )
    assert calls == ["direct", "reference"]
