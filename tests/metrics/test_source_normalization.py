import pytest

from SensibLaw.src.metrics.source_normalization import (
    DEFAULT_NORMALIZATION_THRESHOLDS,
    compute_source_normalization_metrics,
    evaluate_un_adopter_readiness,
    evaluate_live_un_readiness,
    evaluate_world_bank_readiness,
    evaluate_icc_readiness,
)


def test_compute_source_normalization_metrics_flags_incomplete_family():
    families = [
        {
            "id": "congress.gov",
            "contract_complete": True,
            "authority_nodes": 2,
            "provenance_links": ["govinfo"],
            "visible_in_live": True,
            "visible_in_fallback": True,
            "follow_ready": True,
            "translation_aligned": True,
        },
        {
            "id": "govinfo",
            "contract_complete": True,
            "authority_labels": ["official"],
            "provenance_links": ["congress.gov"],
            "visible_in_fallback": True,
            "follow_ready": True,
            "translation_alignment_score": 0.9,
        },
        {
            "id": "unmapped",
            "authority_nodes": 0,
            "provenance_links": [],
            "visible_in_live": False,
            "visible_in_fallback": False,
            "follow_ready": False,
        },
    ]

    result = compute_source_normalization_metrics(families)

    assert result.total_families == 3
    assert result.contract_completeness_share == pytest.approx(2 / 3)
    assert result.authority_clarity_share == pytest.approx(2 / 3)
    assert result.provenance_completeness_share == pytest.approx(2 / 3)
    assert result.live_observability_share == pytest.approx(1 / 3)
    assert result.fallback_observability_share == pytest.approx(2 / 3)
    assert result.live_or_fallback_share == pytest.approx(2 / 3)
    assert result.follow_ready_share == pytest.approx(2 / 3)
    assert result.translation_alignment_share == pytest.approx(2 / 3)
    assert result.normalized is False
    assert any("unmapped" in violation for violation in result.violations)


def test_compute_source_normalization_metrics_can_cross_thresholds():
    families = [
        {
            "id": "congress.gov",
            "contract_complete": True,
            "authority_nodes": 1,
            "provenance_links": ["govinfo"],
            "visible_in_live": True,
            "visible_in_fallback": True,
            "follow_ready": True,
            "translation_alignment_score": 0.95,
        }
        for _ in range(3)
    ]

    result = compute_source_normalization_metrics(
        families,
        thresholds={
            **DEFAULT_NORMALIZATION_THRESHOLDS,
            "contract": 0.3,
            "live_or_fallback": 0.3,
            "follow_ready": 0.3,
            "translation_alignment": 0.3,
        },
    )

    assert result.normalized is True
    assert result.violations == ()


def test_evaluate_un_adopter_readiness():
    families = [
        {
            "id": "united_nations",
            "contract_complete": True,
            "provenance_links": ["security_council"],
            "translation_aligned": True,
            "authority_nodes": 1,
            "visible_in_live": True,
            "visible_in_fallback": True,
            "follow_ready": True,
        }
        for _ in range(2)
    ]

    result = evaluate_un_adopter_readiness(families)

    assert result.normalized is True
    assert result.contract_share == pytest.approx(1.0)
    assert result.provenance_share == pytest.approx(1.0)
    assert result.translation_alignment_share == pytest.approx(1.0)
    assert result.authority_share == pytest.approx(1.0)
    assert result.follow_ready_share == pytest.approx(1.0)
    assert result.violations == ()


def test_evaluate_un_adopter_readiness_blocks_missing_translation():
    families = [
        {
            "id": "un_adopter",
            "contract_complete": True,
            "provenance_links": ["assembly"],
            "translation_aligned": False,
            "authority_nodes": 2,
            "follow_ready": True,
        }
    ]

    result = evaluate_un_adopter_readiness(families)

    assert result.normalized is False
    assert any("translation_alignment" in v for v in result.violations)


def test_evaluate_live_un_readiness_rejects_missing_live_visibility():
    families = [
        {
            "id": "live_un",
            "contract_complete": True,
            "provenance_links": ["assembly"],
            "translation_aligned": True,
            "authority_nodes": 1,
            "visible_in_live": False,
            "visible_in_fallback": True,
            "follow_ready": True,
        }
        for _ in range(2)
    ]

    result = evaluate_live_un_readiness(families)

    assert result.normalized is False
    assert result.live_share == pytest.approx(0.0)
    assert result.live_document_share == pytest.approx(0.0)


def test_evaluate_live_un_readiness_allows_live_coverage():
    families = [
        {
            "id": "live_un",
            "contract_complete": True,
            "provenance_links": ["council"],
            "translation_aligned": True,
            "authority_nodes": 1,
            "visible_in_live": True,
            "visible_in_fallback": True,
            "follow_ready": True,
            "live_document_ready": True,
        }
        for _ in range(3)
    ]

    result = evaluate_live_un_readiness(families)

    assert result.normalized is True
    assert result.live_share == pytest.approx(1.0)
    assert result.translation_alignment_share == pytest.approx(1.0)
    assert result.live_document_share == pytest.approx(1.0)


def test_evaluate_world_bank_readiness_checks_both_live_and_fallback():
    families = [
        {
            "id": "worldbank",
            "contract_complete": True,
            "provenance_links": ["wb-docs"],
            "translation_aligned": True,
            "authority_nodes": 1,
            "visible_in_live": True,
            "visible_in_fallback": True,
            "follow_ready": True,
        }
        for _ in range(3)
    ]

    result = evaluate_world_bank_readiness(families)

    assert result.normalized is True
    assert result.live_share == pytest.approx(1.0)
    assert result.fallbacks_share == pytest.approx(1.0)


def test_evaluate_world_bank_readiness_blocks_missing_fallback():
    families = [
        {
            "id": "worldbank",
            "contract_complete": True,
            "provenance_links": ["wb-docs"],
            "translation_aligned": True,
            "authority_nodes": 1,
            "visible_in_live": True,
            "visible_in_fallback": False,
            "follow_ready": True,
        }
        for _ in range(2)
    ]

    result = evaluate_world_bank_readiness(families)

    assert result.normalized is False
    assert result.fallbacks_share == pytest.approx(0.0)


def test_evaluate_icc_readiness_requires_live_and_fallback():
    families = [
        {
            "id": "icc",
            "contract_complete": True,
            "provenance_links": ["cases"],
            "translation_aligned": True,
            "authority_nodes": 1,
            "visible_in_live": True,
            "visible_in_fallback": True,
            "follow_ready": True,
        }
        for _ in range(2)
    ]

    result = evaluate_icc_readiness(families)

    assert result.normalized is True
    assert result.live_share == pytest.approx(1.0)
    assert result.fallback_share == pytest.approx(1.0)


def test_evaluate_icc_readiness_blocks_incomplete_document():
    families = [
        {
            "id": "icc",
            "contract_complete": False,
            "provenance_links": ["cases"],
            "translation_aligned": True,
            "authority_nodes": 1,
            "visible_in_live": True,
            "visible_in_fallback": True,
            "follow_ready": True,
        }
    ]

    result = evaluate_icc_readiness(families)

    assert result.normalized is False
    assert result.contract_share == pytest.approx(0.0)
