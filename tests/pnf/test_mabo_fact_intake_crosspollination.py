from __future__ import annotations

from src.pnf.mabo_fact_intake_crosspollination import (
    build_mabo_cross_source_fact_probe,
)


def test_mabo_cross_source_probe_reuses_existing_residual_calculus() -> None:
    probe = build_mabo_cross_source_fact_probe()

    assert probe["schema_version"] == "sl.fact_extraction_probe.v0_1"
    assert probe["case_count"] == 2
    assert probe["summary"]["residual_counts"] == {"exact": 2}
    assert probe["summary"]["status_counts"] == {"supported": 2}
    assert probe["summary"]["contested_cases"] == 0
    assert probe["summary"]["abstained_cases"] == 0


def test_mabo_cross_source_exact_meet_does_not_promote_world_truth() -> None:
    probe = build_mabo_cross_source_fact_probe()

    for case in probe["cases"]:
        assert case["aggregate_residual"] == "exact"
        assert case["fact_candidate"]["status"] == "supported"
        assert case["promotion_gate"]["promote_requested"] is False
        assert case["promotion_gate"]["gate_status"] == "not_promoted"
        assert case["authority_policy"] == "review_only"
        assert case["missing_receipts"] == []

    boundary = probe["mabo_alignment_boundary"]
    assert boundary["surface_texts_differ"] is True
    assert boundary["typed_coordinates_human_reviewed"] is True
    assert boundary["shared_coordinate_is_world_truth"] is False
    assert boundary["shared_coordinate_is_party_admission"] is False
    assert boundary["promotion_requested"] is False
    assert boundary["source_provenance_preserved"] is True


def test_mabo_cross_source_probe_preserves_distinct_evidence_provenance() -> None:
    probe = build_mabo_cross_source_fact_probe()
    by_case = {case["case_id"]: case for case in probe["cases"]}

    native_title = by_case["mabo_native_title_cross_source"]
    assert native_title["evidence_comparisons"][0]["provenance"] == [
        "obs:nta-preamble:native-title"
    ]

    terra_nullius = by_case["mabo_terra_nullius_cross_source"]
    assert terra_nullius["evidence_comparisons"][0]["provenance"] == [
        "obs:nta-preamble:terra-nullius"
    ]


def test_existing_fact_probe_authority_boundaries_remain_in_force() -> None:
    probe = build_mabo_cross_source_fact_probe()
    boundary = probe["authority_boundary"]

    assert boundary["raw_sentence_as_fact"] is False
    assert boundary["llm_summary_as_fact"] is False
    assert boundary["predicate_pnf_fibres_gate_comparison"] is True
    assert boundary["facts_require_source_excerpt_statement_observation_receipts"] is True
    assert boundary["promotion_requires_gate"] is True
