from __future__ import annotations

import pytest

from src.runtime.hierarchy_execution_policy import (
    HierarchyExecutionPolicy,
    hierarchy_policy_from_environment,
)


def test_policy_builds_configured_plan() -> None:
    policy = HierarchyExecutionPolicy(leaf_capacity=1024, arity=8)
    plan = policy.build_plan(
        document_ref="document:policy",
        primitive_unit_count=5000,
        unit="atoms",
    )

    assert len(plan.leaf_refs) == 5
    assert plan.leaf_capacity == 1024
    assert plan.arity == 8
    assert plan.depth == 1


def test_policy_reads_environment(monkeypatch) -> None:
    monkeypatch.setenv("SENSIBLAW_HIERARCHY_LEAF_CAPACITY", "2048")
    monkeypatch.setenv("SENSIBLAW_HIERARCHY_ARITY", "4")

    policy = hierarchy_policy_from_environment()

    assert policy.leaf_capacity == 2048
    assert policy.arity == 4


def test_policy_rejects_invalid_arity(monkeypatch) -> None:
    monkeypatch.setenv("SENSIBLAW_HIERARCHY_ARITY", "1")

    with pytest.raises(ValueError, match="at least two"):
        hierarchy_policy_from_environment()
