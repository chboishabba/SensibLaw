from __future__ import annotations

from scripts.compare_follow_quality_reports import build_comparison


def test_build_comparison_reports_summary_and_bucket_deltas() -> None:
    before = {
        "schema_version": "wiki_random_article_ingest_coverage_report_v0_7",
        "summary": {
            "average_follow_yield_metrics": {
                "follow_target_quality_score": 0.5,
                "followed_link_relevance_score": 0.4,
            },
            "average_best_path_metrics": {"best_path_vs_avg_gap": 0.03},
            "average_two_hop_metrics": {"hop_quality_decay": 0.01},
            "follow_failure_bucket_counts": {"list_like_follow": 10, "low_information_gain_follow": 5},
            "specificity_reason_counts": {"umbrella_title": 4},
            "information_gain_reason_counts": {"year_prefixed_title": 2},
        },
        "pages": [
            {
                "title": "Example",
                "follow_yield_metrics": {"follow_target_quality_score": 0.5},
                "best_path_metrics": {"best_path_vs_avg_gap": 0.03},
            }
        ],
    }
    after = {
        "schema_version": "wiki_random_article_ingest_coverage_report_v0_9",
        "summary": {
            "average_follow_yield_metrics": {
                "follow_target_quality_score": 0.6,
                "followed_link_relevance_score": 0.35,
            },
            "average_best_path_metrics": {"best_path_vs_avg_gap": 0.05},
            "average_two_hop_metrics": {"hop_quality_decay": 0.0},
            "follow_failure_bucket_counts": {"list_like_follow": 8, "low_information_gain_follow": 7},
            "specificity_reason_counts": {"umbrella_title": 2},
            "information_gain_reason_counts": {"year_prefixed_title": 4},
        },
        "pages": [
            {
                "title": "Example",
                "follow_yield_metrics": {"follow_target_quality_score": 0.6},
                "best_path_metrics": {"best_path_vs_avg_gap": 0.05},
            }
        ],
    }

    comparison = build_comparison(before, after)
    assert comparison["metric_deltas"]["average_follow_yield_metrics.follow_target_quality_score"]["delta"] == 0.1
    assert comparison["bucket_deltas"]["list_like_follow"]["delta"] == -2
    assert comparison["bucket_deltas"]["low_information_gain_follow"]["delta"] == 2
    assert comparison["specificity_reason_deltas"]["umbrella_title"]["delta"] == -2
    assert comparison["information_gain_reason_deltas"]["year_prefixed_title"]["delta"] == 2
    assert comparison["shared_page_count"] == 1
