from __future__ import annotations

from scripts.analyze_follow_quality_reports import _infer_follow_bucket
from scripts.report_wiki_random_article_ingest_coverage import compute_follow_target_quality


def test_infer_follow_bucket_prefers_low_information_when_cooccurring() -> None:
    detail = {
        "non_list_score": 0.0,
        "richness_score": 0.2,
        "regime_similarity_score": 0.3,
        "information_gain_score": 0.2,
    }
    assert _infer_follow_bucket(detail) == "low_information_gain_follow"


def test_generic_continuation_routes_to_low_information_follow_bucket() -> None:
    details = compute_follow_target_quality(
        {
            "title": "Fernandes",
            "key_terms": ["fernandes"],
            "regime": {"narrative": 0.2, "descriptive": 0.7, "formal": 0.1},
        },
        {
            "title": "2018 Oracle Challenger Series – Chicago",
            "raw_text": "2018 Oracle Challenger Series in Chicago.",
            "article_sentence_count": 7,
            "observation_count": 2,
            "article_aao_event_count": 2,
        },
    )

    assert details["list_follow_subtype"] == "generic_continuation_routing_to_low_information"
    assert details["list_like_penalty_active"] is False
    assert "low_information_gain_follow" in details["quality_flags"]
