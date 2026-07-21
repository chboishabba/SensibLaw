from __future__ import annotations

from src.pnf.constraint_worklist import evaluate_constraint_worklist
from src.policy.algebra import FactorConstraint


def _constraint(ref: str, source: str, target: str) -> FactorConstraint:
    return FactorConstraint(
        constraint_ref=ref,
        source_factor_refs=(source,),
        target_factor_refs=(target,),
        relation_type="syntactic_subject_of",
        evidence_refs=(f"evidence:{ref}",),
    )


def test_initial_constraint_fixed_point_evaluates_all_constraints() -> None:
    result = evaluate_constraint_worklist(
        document_ref="document:1",
        factor_refs=("factor:a", "factor:b", "factor:c"),
        constraints=(
            _constraint("constraint:ab", "factor:a", "factor:b"),
            _constraint("constraint:bc", "factor:b", "factor:c"),
        ),
    )

    assert {row.constraint_ref for row in result.assessments} == {
        "constraint:ab",
        "constraint:bc",
    }
    assert result.fixed_point_rounds == 1
    assert result.to_dict()["pending_work_items"] == 0


def test_targeted_change_evaluates_only_incident_constraints() -> None:
    result = evaluate_constraint_worklist(
        document_ref="document:1",
        factor_refs=("factor:a", "factor:b", "factor:c"),
        constraints=(
            _constraint("constraint:ab", "factor:a", "factor:b"),
            _constraint("constraint:bc", "factor:b", "factor:c"),
        ),
        changed_factor_refs=("factor:c",),
    )

    assert [row.constraint_ref for row in result.assessments] == [
        "constraint:bc"
    ]
    assert [row.constraint_ref for row in result.work_items] == [
        "constraint:bc"
    ]


def test_unrelated_change_does_not_fall_back_to_full_scan() -> None:
    result = evaluate_constraint_worklist(
        document_ref="document:1",
        factor_refs=("factor:a", "factor:b"),
        constraints=(
            _constraint("constraint:ab", "factor:a", "factor:b"),
        ),
        changed_factor_refs=("factor:unrelated",),
    )

    assert result.assessments == ()
    assert result.work_items == ()
    assert result.fixed_point_rounds == 0
