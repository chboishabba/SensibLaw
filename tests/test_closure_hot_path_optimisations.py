from __future__ import annotations

from collections.abc import Iterable

from src.pnf.factor_proposals import FactorProposal
from src.policy.closure_hot_path_execution import auto_semantic_process_workers
from src.policy.reduction_hot_path_execution import reduce_factor_proposals_bitset


def _proposal(*, ordinal: int, roles: dict[str, str]) -> FactorProposal:
    return FactorProposal(
        document_ref="document:test",
        source_revision_ref="source:test",
        factor_type_ref="semantic.test",
        source_span_refs=("scope:test",),
        input_observation_refs=(),
        dependency_factor_refs=(),
        structural_signature="signature:test",
        role_bindings=roles,
        qualifier_state={},
        producer_contract="producer:test",
        declaration_revision="v1",
        candidate_payload={"ordinal": ordinal},
        scope_ref="scope:test",
    )


def _legacy_first_match_groups(
    proposals: Iterable[FactorProposal],
) -> tuple[tuple[tuple[str, ...], ...], int]:
    ordered = sorted(proposals, key=lambda row: row.proposal_ref)
    groups: list[list[FactorProposal]] = []
    group_roles: list[dict[str, str]] = []
    comparisons = 0
    for proposal in ordered:
        matched_index: int | None = None
        for index, _group in enumerate(groups):
            comparisons += 1
            occupied = group_roles[index]
            if all(
                occupied.get(role, value) == value
                for role, value in proposal.role_bindings.items()
            ):
                matched_index = index
                break
        if matched_index is None:
            groups.append([proposal])
            group_roles.append(dict(proposal.role_bindings))
        else:
            groups[matched_index].append(proposal)
            group_roles[matched_index].update(proposal.role_bindings)
    return (
        tuple(
            tuple(sorted(row.proposal_ref for row in group))
            for group in groups
        ),
        comparisons,
    )


def test_bitset_reducer_preserves_greedy_first_match_partition() -> None:
    # Partial role maps deliberately exercise the non-transitive compatibility
    # shape that makes a naive associative incremental reducer unsound.
    proposals = (
        _proposal(ordinal=1, roles={"x": "A"}),
        _proposal(ordinal=2, roles={"y": "B"}),
        _proposal(ordinal=3, roles={"x": "C"}),
        _proposal(ordinal=4, roles={"x": "A", "z": "D"}),
        _proposal(ordinal=5, roles={"y": "E"}),
        _proposal(ordinal=6, roles={}),
        _proposal(ordinal=7, roles={"x": "C", "y": "B"}),
    )
    expected_groups, expected_comparisons = _legacy_first_match_groups(proposals)

    reduction = reduce_factor_proposals_bitset(
        document_ref="document:test",
        proposals=proposals,
    )
    actual_groups = tuple(
        factor.proposal_refs
        for factor in sorted(
            reduction.factors,
            key=lambda row: min(row.proposal_refs),
        )
    )

    # Factor hashes sort independently of group creation order; compare the
    # canonical proposal-ref sets rather than factor-ref order.
    assert sorted(actual_groups) == sorted(expected_groups)
    assert reduction.metrics["candidate_comparisons"] == expected_comparisons
    assert reduction.metrics["compatibility_lookup"] == "exact_first_match_bitset"


def test_bitset_reducer_preserves_factor_and_residual_identity_under_reordering() -> None:
    proposals = tuple(
        _proposal(ordinal=index, roles={"role": value})
        for index, value in enumerate(("A", "B", "A", "C", "B"), start=1)
    )
    forward = reduce_factor_proposals_bitset(
        document_ref="document:test", proposals=proposals
    )
    reverse = reduce_factor_proposals_bitset(
        document_ref="document:test", proposals=reversed(proposals)
    )

    assert tuple(row.factor_ref for row in forward.factors) == tuple(
        row.factor_ref for row in reverse.factors
    )
    assert tuple(row.residual_ref for row in forward.residuals) == tuple(
        row.residual_ref for row in reverse.residuals
    )


def test_auto_process_width_is_bounded_and_respects_override(monkeypatch) -> None:
    monkeypatch.delenv("SENSIBLAW_SEMANTIC_PROCESS_WORKERS", raising=False)
    monkeypatch.setenv("SENSIBLAW_SEMANTIC_PROCESS_AUTO_MAX", "3")
    width = auto_semantic_process_workers()
    assert 1 <= width <= 3

    monkeypatch.setenv("SENSIBLAW_SEMANTIC_PROCESS_WORKERS", "7")
    assert auto_semantic_process_workers() == 7


def test_installed_bounded_solver_uses_operational_process_aware_wrapper() -> None:
    # Importing src.policy installs strategies in order. The regression being
    # pinned here was a stale module-global import in bounded execution.
    from src.policy import bounded_operational_execution as bounded
    from src.policy import operational_corpus_compilation as operational

    assert bounded.solve_operator_job is operational.solve_operator_job


def test_dependency_free_coalescing_is_fail_closed_for_declared_dependencies() -> None:
    from src.policy.closure_hot_path_execution import (
        _dirty_proposals_are_dependency_free,
    )
    from src.pnf.bounded_streaming_owner import BoundedStreamingSemanticOwner

    owner = BoundedStreamingSemanticOwner(document_ref="document:test")
    independent = _proposal(ordinal=1, roles={"x": "A"})
    owner.admit_proposals((independent,), stage="base")
    assert _dirty_proposals_are_dependency_free(owner) is True

    dependent = FactorProposal(
        document_ref="document:test",
        source_revision_ref="source:test",
        factor_type_ref="semantic.other",
        source_span_refs=("scope:other",),
        input_observation_refs=(),
        dependency_factor_refs=("factor:required",),
        structural_signature="signature:other",
        role_bindings={"x": "B"},
        qualifier_state={},
        producer_contract="producer:test",
        declaration_revision="v1",
        candidate_payload={"ordinal": 2},
        scope_ref="scope:other",
    )
    owner.admit_proposals((dependent,), stage="base")
    assert _dirty_proposals_are_dependency_free(owner) is False
