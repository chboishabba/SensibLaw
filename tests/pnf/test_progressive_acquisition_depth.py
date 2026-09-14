from __future__ import annotations

from src.pnf.federated_zos_acquisition import AcquisitionPolicy, SourceClass
from src.pnf.progressive_acquisition_depth import (
    AcquisitionDepth,
    AcquisitionObservation,
    choose_next_depth,
    primary_authority_payment_eligible,
)


def test_exact_residual_never_deepens() -> None:
    decision = choose_next_depth(
        residual_level="exact",
        current_depth=AcquisitionDepth.SEARCH_RESULT,
        policy=AcquisitionPolicy.public_research(corpus_ref="public:mabo"),
        source_class=SourceClass.SECONDARY_SOURCE,
        network_requests_used=1,
    )
    assert decision.should_acquire is False
    assert decision.next_depth is None
    assert decision.reason == "residual-already-paid"


def test_live_residual_deepens_search_result_to_abstract_before_full_text() -> None:
    policy = AcquisitionPolicy.public_research(corpus_ref="public:science")
    first = choose_next_depth(
        residual_level="partial",
        current_depth=AcquisitionDepth.SEARCH_RESULT,
        policy=policy,
        source_class=SourceClass.MEASUREMENT_SOURCE,
        network_requests_used=1,
    )
    second = choose_next_depth(
        residual_level="partial",
        current_depth=AcquisitionDepth.ABSTRACT,
        policy=policy,
        source_class=SourceClass.MEASUREMENT_SOURCE,
        network_requests_used=2,
    )
    assert first.should_acquire is True
    assert first.next_depth is AcquisitionDepth.ABSTRACT
    assert second.next_depth is AcquisitionDepth.FULL_SOURCE


def test_budget_exhaustion_stops_deepening_without_fabricating_payment() -> None:
    policy = AcquisitionPolicy(
        consumer_ref="tiny-budget",
        corpus_ref="public:test",
        privacy=AcquisitionPolicy.public_research(corpus_ref="x").privacy,
        allowed_source_classes=frozenset({SourceClass.SECONDARY_SOURCE}),
        allow_remote_storage=False,
        allow_remote_compute=False,
        allow_remote_discovery=True,
        allow_public_ontology_candidates=False,
        advertise_private_corpus=False,
        max_depth=8,
        network_budget=2,
        storage_budget_bytes=1024,
    )
    decision = choose_next_depth(
        residual_level="contradiction",
        current_depth=AcquisitionDepth.ABSTRACT,
        policy=policy,
        source_class=SourceClass.SECONDARY_SOURCE,
        network_requests_used=2,
    )
    assert decision.should_acquire is False
    assert decision.next_depth is None
    assert decision.reason == "network-budget-exhausted"
    assert decision.creates_evidence_payment is False


def test_strict_legal_primary_authority_requires_full_source_for_payment_eligibility() -> None:
    policy = AcquisitionPolicy.legal_strict(corpus_ref="matter:mabo")
    snippet = AcquisitionObservation(
        source_ref="HCA:Mabo:search-result",
        source_class=SourceClass.PRIMARY_AUTHORITY,
        depth=AcquisitionDepth.SEARCH_RESULT,
        source_identity_verified=True,
        exact_source_span_available=False,
    )
    abstract = AcquisitionObservation(
        source_ref="HCA:Mabo:headnote",
        source_class=SourceClass.PRIMARY_AUTHORITY,
        depth=AcquisitionDepth.ABSTRACT,
        source_identity_verified=True,
        exact_source_span_available=False,
    )
    full = AcquisitionObservation(
        source_ref="HCA:Mabo:judgment",
        source_class=SourceClass.PRIMARY_AUTHORITY,
        depth=AcquisitionDepth.FULL_SOURCE,
        source_identity_verified=True,
        exact_source_span_available=True,
    )
    assert primary_authority_payment_eligible(policy, snippet) is False
    assert primary_authority_payment_eligible(policy, abstract) is False
    assert primary_authority_payment_eligible(policy, full) is True


def test_full_source_still_does_not_itself_promote_truth() -> None:
    policy = AcquisitionPolicy.legal_strict(corpus_ref="matter:mabo")
    full = AcquisitionObservation(
        source_ref="HCA:Mabo:judgment",
        source_class=SourceClass.PRIMARY_AUTHORITY,
        depth=AcquisitionDepth.FULL_SOURCE,
        source_identity_verified=True,
        exact_source_span_available=True,
    )
    assert primary_authority_payment_eligible(policy, full) is True
    assert full.semantic_authority is False
    assert full.claim_truth_promoted is False
    assert full.review_required is True
