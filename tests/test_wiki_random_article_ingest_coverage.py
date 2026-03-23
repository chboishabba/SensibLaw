from __future__ import annotations

import math
import json
from pathlib import Path

from scripts.report_wiki_random_article_ingest_coverage import (
    _event_has_action,
    _event_has_object,
    _page_row_from_outputs,
    compute_follow_target_quality,
    compute_information_gain_score,
    compute_non_list_score,
    compute_path_score,
    compute_regime_similarity_score,
    compute_richness_score,
    build_article_ingest_report,
    build_article_sentence_surface,
    main,
    score_snapshot_payload,
)


def _write_snapshot(tmp_path: Path, *, name: str, title: str, text: str, links: list[str] | None = None) -> Path:
    path = tmp_path / name
    path.write_text(
        json.dumps(
            {
                "wiki": "enwiki",
                "title": title,
                "pageid": 1,
                "revid": 100,
                "source_url": f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
                "links": list(links or []),
                "wikitext": text,
            }
        ),
        encoding="utf-8",
    )
    return path


def test_build_article_sentence_surface_keeps_non_anchored_sentences() -> None:
    surface = build_article_sentence_surface(
        {
            "title": "Example",
            "wikitext": (
                "== Early life ==\n"
                "Jane patted the cat in Brisbane after lunch.\n"
                "On May 5, 2021, Dr Smith performed surgery on the plaintiff."
            ),
        }
    )

    texts = [row["text"] for row in surface["events"]]
    anchor_statuses = {row["anchor_status"] for row in surface["events"]}
    assert any("Jane patted the cat in Brisbane after lunch." in text for text in texts)
    assert len(surface["events"]) >= 2
    assert "none" in anchor_statuses
    assert "explicit" in anchor_statuses


def test_follow_target_quality_and_path_scoring_match_requested_formula() -> None:
    root = {
        "regime": {"narrative": 0.1, "descriptive": 0.8, "formal": 0.1},
        "key_terms": ["agrega", "project", "repository", "schools"],
        "raw_text": "Agrega is a project that connects schools.",
    }
    follow = {
        "article_sentence_count": 20,
        "observation_count": 10,
        "article_aao_event_count": 5,
        "regime": {"narrative": 0.2, "descriptive": 0.7, "formal": 0.1},
        "key_terms": ["project", "repository", "schools", "standards"],
        "raw_text": "This descriptive page outlines a project and repository standards.",
    }

    richness_score = compute_richness_score(follow)
    non_list_score = compute_non_list_score(follow)
    regime_similarity_score = compute_regime_similarity_score(root, follow)
    information_gain_score = compute_information_gain_score(root, follow)
    details = compute_follow_target_quality(root, follow)
    expected_follow_target_quality = round(
        min(
            1.0,
            0.35 * richness_score
            + 0.25 * non_list_score
            + 0.20 * regime_similarity_score
            + 0.20 * information_gain_score,
        ),
        6,
    )

    assert math.isclose(details["richness_score"], 0.436667, abs_tol=1e-6)
    assert math.isclose(details["non_list_score"], 1.0, abs_tol=1e-6)
    assert math.isclose(details["regime_similarity_score"], 0.59, abs_tol=1e-6)
    assert math.isclose(details["information_gain_score"], 0.916667, abs_tol=1e-6)
    assert math.isclose(details["follow_target_quality_score"], expected_follow_target_quality, abs_tol=1e-6)

    hop2 = {
        "regime": {"narrative": 0.3, "descriptive": 0.6, "formal": 0.1},
        "key_terms": ["project", "repository", "standards", "schools"],
        "raw_text": "This page extends the project repository discussion.",
    }
    path_score = compute_path_score(root, follow, hop2, 0.7, 0.4)
    expected_path_score = round(
        min(
            1.0,
            0.4 * 0.7
            + 0.4 * 0.4
            + 0.2
            * (
                0.5 * compute_regime_similarity_score(root, follow)
                + 0.5 * compute_regime_similarity_score(follow, hop2)
            ),
        ),
        6,
    )
    assert math.isclose(path_score, expected_path_score, abs_tol=1e-6)


def test_score_snapshot_payload_reports_canonical_state_and_follow_usage(tmp_path: Path) -> None:
    follow_snapshot_path = _write_snapshot(
        tmp_path,
        name="cat.json",
        title="Cat",
        text="A cat is a small domesticated carnivorous mammal.",
    )
    row = score_snapshot_payload(
        {
            "title": "Article example",
            "source_url": "https://en.wikipedia.org/wiki/Article_example",
            "links": ["Cat"],
            "wikitext": (
                "== Campaign ==\n"
                "Jane performed surgery on the plaintiff in Brisbane.\n"
                "On May 5, 2021, the court ordered damages."
            ),
        },
        follow_rows=[{"title": "Cat", "snapshot_path": str(follow_snapshot_path)}],
        max_follow_links_per_page=2,
        no_spacy=True,
    )

    assert row["article_sentence_count"] >= 2
    assert row["observation_count"] >= row["article_aao_event_count"]
    assert row["article_aao_event_count"] >= 1
    assert row["action_event_count"] >= 1
    assert row["followed_snapshot_count"] == 1
    assert row["scores"]["article_ingest_score"] > 0.0
    assert row["honesty_scores"]["article_ingest_honest_score"] > 0.0
    assert row["calibration_scores"]["article_ingest_calibrated_score"] > 0.0
    assert row["follow_yield_metrics"]["follow_yield_score"] is not None
    assert row["follow_yield_metrics"]["follow_target_quality_score"] is not None
    expected_follow_yield = round(
        (
            float(row["follow_yield_metrics"]["followed_link_relevance_score"])
            + float(row["follow_yield_metrics"]["follow_target_quality_score"])
        )
        / 2.0,
        6,
    )
    assert row["follow_yield_metrics"]["follow_yield_score"] == expected_follow_yield
    assert row["scores"]["observation_density_score"] > 0.0
    assert row["density_metrics"]["observations_per_sentence"] > 0.0
    assert row["timeline_projection"]["event_count"] == row["article_aao_event_count"]
    assert "none" in row["timeline_projection"]["anchor_status_counts"] or "explicit" in row["timeline_projection"]["anchor_status_counts"]
    assert row["timeline_readiness"]["scores"]["overall_readiness_score"] > 0.0
    assert row["timeline_honesty"]["timeline_honesty_score"] is not None
    assert row["page_profile"]["family"] in {"general", "project_institution", "facility"}


def test_build_article_ingest_report_aggregates_pages(tmp_path: Path) -> None:
    strong_path = _write_snapshot(
        tmp_path,
        name="strong.json",
        title="Strong example",
        links=["Cat"],
        text=(
            "== Campaign ==\n"
            "Jane performed surgery on the plaintiff in Brisbane.\n"
            "On May 5, 2021, the court ordered damages."
        ),
    )
    cat_path = _write_snapshot(
        tmp_path,
        name="cat.json",
        title="Cat",
        text="A cat is a small domesticated carnivorous mammal.",
    )
    weak_path = _write_snapshot(
        tmp_path,
        name="weak.json",
        title="Weak example",
        text="Jane patted the cat in Brisbane after lunch.",
    )
    manifest = {
        "generated_at": "2026-03-22T00:00:00Z",
        "wiki": "enwiki",
        "requested_count": 2,
        "sampled_count": 2,
        "namespace": 0,
        "follow_hops": 1,
        "max_follow_links_per_page": 2,
        "samples": [
            {"snapshot_path": str(strong_path), "followed_samples": [{"title": "Cat", "snapshot_path": str(cat_path)}]},
            {"snapshot_path": str(weak_path), "followed_samples": []},
        ],
    }

    report = build_article_ingest_report(manifest, emit_page_rows=True, no_spacy=True)
    assert report["schema_version"] == "wiki_random_article_ingest_coverage_report_v0_6"
    assert report["supported_surface"]["canonical_state_surface"] == "wiki_article_state_v0_1"
    assert report["summary"]["page_count"] == 2
    assert report["summary"]["pages_with_article_sentences"] == 2
    assert report["summary"]["pages_with_article_aao_events"] >= 1
    assert report["summary"]["pages_with_followed_snapshots"] == 1
    assert "average_honesty_scores" in report["summary"]
    assert "average_regime" in report["summary"]
    assert "dominant_regime_counts" in report["summary"]
    assert "average_regime_honesty_scores" in report["summary"]
    assert "average_follow_yield_metrics" in report["summary"]
    assert "average_follow_target_quality" in report["summary"]
    assert "two_hop_metrics" in report["summary"]
    assert "best_path_metrics" in report["summary"]
    assert "average_regime_calibration_scores" in report["summary"]
    assert "average_calibration_scores" in report["summary"]
    assert "average_density_metrics" in report["summary"]
    assert "average_timeline_honesty" in report["summary"]
    assert "page_family_counts" in report["summary"]
    assert "page_family_honesty_issue_counts" in report["summary"]
    assert "page_family_calibration_issue_counts" in report["summary"]
    assert len(report["pages"]) == 2


def test_article_ingest_main_writes_report(tmp_path: Path, capsys) -> None:
    snapshot_path = _write_snapshot(
        tmp_path,
        name="article.json",
        title="Article example",
        links=["Cat"],
        text=(
            "== Campaign ==\n"
            "Jane performed surgery on the plaintiff in Brisbane.\n"
            "On May 5, 2021, the court ordered damages."
        ),
    )
    manifest_path = tmp_path / "manifest.json"
    report_path = tmp_path / "report.json"
    cat_path = _write_snapshot(
        tmp_path,
        name="cat.json",
        title="Cat",
        text="A cat is a small domesticated carnivorous mammal.",
    )
    manifest_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-03-22T00:00:00Z",
                "wiki": "enwiki",
                "requested_count": 1,
                "sampled_count": 1,
                "namespace": 0,
                "follow_hops": 1,
                "max_follow_links_per_page": 2,
                "samples": [
                    {
                        "snapshot_path": str(snapshot_path),
                        "followed_samples": [{"title": "Cat", "snapshot_path": str(cat_path)}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "--manifest",
            str(manifest_path),
            "--output",
            str(report_path),
            "--emit-page-rows",
            "--no-spacy",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert report_path.exists()
    assert payload["summary"]["page_count"] == 1
    assert payload["pages"][0]["title"] == "Article example"
    assert payload["schema_version"] == "wiki_random_article_ingest_coverage_report_v0_6"


def test_event_has_action_and_object_detection() -> None:
    assert not _event_has_action({})
    assert _event_has_action({"action": "jumped"})
    assert _event_has_action({"steps": [{"action": "ran"}]})

    assert not _event_has_object({})
    assert _event_has_object({"objects": ["fence"]})
    assert _event_has_object({"entity_objects": ["Alice"]})
    assert _event_has_object({"steps": [{"numeric_objects": ["5"]}]})


def test_page_row_from_outputs_flags_missing_surfaces() -> None:
    payload = {"title": "Test", "links": ["foo"]}
    article_state = {
        "sentence_units": [
            {"event_id": "art:0001", "text": "Sentence one.", "anchor_status": "none"},
            {"event_id": "art:0002", "text": "Sentence two.", "anchor_status": "none"},
        ],
        "observations": [{"observation_id": "obs1"}],
        "event_candidates": [
            {
                "event_id": "art:0001",
                "actors": [{"text": "Alice"}],
                "action": "",
                "objects": [],
                "anchor_status": "none",
            }
        ],
        "timeline_projection": [{"event_id": "art:0001", "order_index": 1, "anchor_status": "none"}],
    }

    row = _page_row_from_outputs(
        payload,
        article_state,
        {},
        {},
        follow_rows=[],
        max_follow_links_per_page=1,
    )

    issues = row["issues"]
    assert "no_action_surface" in issues
    assert "no_object_surface" in issues
    assert "follow_budget_unused" in issues
    assert "no_actor_surface" not in issues
    assert "timeline_mostly_undated" in row["honesty_issues"]

    test_payload_no_sentences = {"title": "Test 2"}
    row_no_sentences = _page_row_from_outputs(
        test_payload_no_sentences,
        {"sentence_units": [], "observations": [], "event_candidates": [], "timeline_projection": []},
        {},
        {},
        follow_rows=[],
        max_follow_links_per_page=0,
    )
    assert "no_article_sentences" in row_no_sentences["issues"]

    row_no_aao = _page_row_from_outputs(
        test_payload_no_sentences,
        {"sentence_units": article_state["sentence_units"], "observations": [], "event_candidates": [], "timeline_projection": []},
        {},
        {},
        follow_rows=[],
        max_follow_links_per_page=0,
    )
    assert "article_sentences_without_aao_events" in row_no_aao["issues"]

    row_no_actor = _page_row_from_outputs(
        test_payload_no_sentences,
        {
            "sentence_units": article_state["sentence_units"],
            "observations": [],
            "event_candidates": [{"event_id": "art:0001", "action": "happened", "anchor_status": "none"}],
            "timeline_projection": [{"event_id": "art:0001", "order_index": 1, "anchor_status": "none"}],
        },
        {},
        {},
        follow_rows=[],
        max_follow_links_per_page=0,
    )
    assert "no_actor_surface" in row_no_actor["issues"]


def test_page_row_from_outputs_penalizes_explosion_hygiene_and_weak_binding() -> None:
    payload = {"title": "Noisy Test", "links": []}
    article_state = {
        "sentence_units": [
            {"event_id": "art:0001", "text": "Alpha.Beta [12]", "anchor_status": "none"},
        ],
        "observations": [{"observation_id": f"obs:{index:04d}"} for index in range(20)],
        "event_candidates": [
            {
                "event_id": "art:0001",
                "text": "Alpha.Beta [12]",
                "actors": [{"text": "Alice"}],
                "action": "announce",
                "steps": [{"action": "announce"}],
                "objects": [],
                "anchor_status": "none",
            }
        ],
        "timeline_projection": [{"event_id": "art:0001", "order_index": 1, "anchor_status": "none"}],
    }

    row = _page_row_from_outputs(
        payload,
        article_state,
        {},
        {},
        follow_rows=[],
        max_follow_links_per_page=0,
    )

    assert row["honesty_scores"]["observation_explosion_score"] == 0.0
    assert row["honesty_scores"]["text_hygiene_score"] == 0.0
    assert row["honesty_scores"]["actor_action_binding_score"] == 0.0
    assert row["honesty_scores"]["object_binding_score"] == 0.0
    assert row["honesty_scores"]["article_ingest_honest_score"] == 0.0
    assert row["density_metrics"]["observations_per_sentence"] == 20.0
    assert row["density_metrics"]["observations_per_event"] == 20.0
    assert row["text_hygiene_warnings"][0]["reason"] in {"citation_tail_residue", "smashed_sentence_join"}
    assert "observation_explosion_high" in row["honesty_issues"]
    assert "weak_actor_action_binding" in row["honesty_issues"]
    assert "weak_object_binding" in row["honesty_issues"]


def test_page_row_from_outputs_reports_calibration_metrics_and_page_family() -> None:
    payload = {
        "title": "Example Project",
        "categories": ["Category:Educational projects"],
        "links": ["Alice", "Bob", "digital repository"],
    }
    article_state = {
        "sentence_units": [
            {
                "event_id": "art:0001",
                "text": "The Example Project is a digital repository for schools.",
                "anchor_status": "none",
                "links": ["digital repository"],
            },
            {
                "event_id": "art:0002",
                "text": "According to Alice, Bob denied the claim.",
                "anchor_status": "none",
                "links": ["Alice", "Bob"],
            },
        ],
        "observations": [{"observation_id": "obs1"}, {"observation_id": "obs2"}],
        "event_candidates": [
            {
                "event_id": "art:0001",
                "text": "The Example Project is a digital repository for schools.",
                "actors": [],
                "action": "",
                "objects": [],
                "anchor_status": "none",
            },
            {
                "event_id": "art:0002",
                "text": "According to Alice, Bob denied the claim.",
                "actors": [{"text": "Bob"}],
                "action": "deny",
                "objects": ["claim"],
                "attributions": [{"attribution_type": "according_to", "attributed_actor_id": "Alice"}],
                "claim_bearing": True,
                "anchor_status": "none",
            },
        ],
        "timeline_projection": [
            {"event_id": "art:0001", "order_index": 1, "anchor_status": "none"},
            {"event_id": "art:0002", "order_index": 2, "anchor_status": "none"},
        ],
        "regime": {"narrative": 0.1, "descriptive": 0.8, "formal": 0.1},
    }

    row = _page_row_from_outputs(
        payload,
        article_state,
        {},
        {},
        follow_rows=[{"title": "Alice"}],
        max_follow_links_per_page=1,
    )

    assert row["page_profile"]["family"] == "project_institution"
    assert row["dominant_regime"] in {"descriptive", "formal"}
    assert row["regime"]["descriptive"] > row["regime"]["narrative"]
    assert row["abstention_metrics"]["abstention_calibration_score"] == 1.0
    assert row["link_metrics"]["root_link_relevance_score"] == 0.666667
    assert row["link_metrics"]["followed_link_relevance_score"] == 1.0
    assert row["claim_attribution_metrics"]["claim_attribution_grounding_score"] == 1.0
    assert row["calibration_scores"]["calibration_multiplier"] == 0.888889
    assert row["calibration_scores"]["article_ingest_calibrated_score"] > 0.0
    assert row["regime_adjusted_scores"]["article_ingest_honest_score"] >= row["honesty_scores"]["article_ingest_honest_score"]
    assert row["regime_calibration_scores"]["article_ingest_calibrated_score"] >= row["calibration_scores"]["article_ingest_calibrated_score"]
    assert row["calibration_issues"] == []


def test_page_row_from_outputs_penalizes_forced_structural_extraction_and_low_link_relevance() -> None:
    payload = {
        "title": "Example Moth",
        "categories": ["Category:Moths described in 1900"],
        "links": ["Geometridae", "North America", "Wingspan"],
    }
    article_state = {
        "sentence_units": [
            {
                "event_id": "art:0001",
                "text": "Example moth is a species of moth of the family Geometridae.",
                "anchor_status": "none",
                "links": ["Geometridae", "North America", "Wingspan"],
            }
        ],
        "observations": [{"observation_id": "obs1"}],
        "event_candidates": [
            {
                "event_id": "art:0001",
                "text": "Example moth is a species of moth of the family Geometridae.",
                "actors": [{"text": "Example moth"}],
                "action": "fork",
                "objects": [],
                "anchor_status": "none",
            }
        ],
        "timeline_projection": [{"event_id": "art:0001", "order_index": 1, "anchor_status": "none"}],
    }

    row = _page_row_from_outputs(
        payload,
        article_state,
        {},
        {},
        follow_rows=[],
        max_follow_links_per_page=0,
    )

    assert row["page_profile"]["family"] == "species_taxonomy"
    assert row["dominant_regime"] in {"descriptive", "narrative"}
    assert row["abstention_metrics"]["abstention_calibration_score"] == 0.0
    assert row["link_metrics"]["root_link_relevance_score"] == 0.0
    assert "forced_structural_extraction" in row["calibration_issues"]
    assert "low_link_relevance" in row["calibration_issues"]


def test_page_row_from_outputs_detects_formal_regime_bias() -> None:
    payload = {
        "title": "Formal Example",
        "links": ["Compact space"],
    }
    article_state = {
        "sentence_units": [
            {
                "event_id": "art:0001",
                "text": "Theorem. Let X be a compact space.",
                "anchor_status": "none",
                "links": ["Compact space"],
            },
            {
                "event_id": "art:0002",
                "text": "There exists a continuous function f.",
                "anchor_status": "none",
                "links": [],
            },
        ],
        "observations": [{"observation_id": "obs1"}, {"observation_id": "obs2"}],
        "event_candidates": [
            {
                "event_id": "art:0001",
                "text": "Theorem. Let X be a compact space.",
                "actors": [],
                "action": "",
                "objects": [],
                "anchor_status": "none",
            },
            {
                "event_id": "art:0002",
                "text": "There exists a continuous function f.",
                "actors": [],
                "action": "",
                "objects": [],
                "anchor_status": "none",
            },
        ],
        "timeline_projection": [
            {"event_id": "art:0001", "order_index": 1, "anchor_status": "none"},
            {"event_id": "art:0002", "order_index": 2, "anchor_status": "none"},
        ],
        "regime": {"narrative": 0.1, "descriptive": 0.2, "formal": 0.7},
    }

    row = _page_row_from_outputs(
        payload,
        article_state,
        {},
        {},
        follow_rows=[],
        max_follow_links_per_page=0,
    )

    assert row["regime"]["formal"] > row["regime"]["narrative"]
    assert row["regime"]["formal"] > row["regime"]["descriptive"]
    assert row["regime_adjusted_scores"]["article_ingest_honest_score"] >= row["honesty_scores"]["article_ingest_honest_score"]


def test_page_row_from_outputs_classifies_biography_family() -> None:
    payload = {
        "title": "Jane Example",
        "categories": ["Category:1903 births", "Category:1976 deaths"],
    }
    article_state = {
        "sentence_units": [
            {
                "event_id": "art:0001",
                "text": "Jane Example (1903-1976) was a British intelligence officer.",
                "anchor_status": "weak",
                "links": [],
            }
        ],
        "observations": [{"observation_id": "obs1"}],
        "event_candidates": [
            {
                "event_id": "art:0001",
                "text": "Jane Example (1903-1976) was a British intelligence officer.",
                "actors": [{"text": "Jane Example"}],
                "action": "",
                "objects": [],
                "anchor_status": "weak",
            }
        ],
        "timeline_projection": [{"event_id": "art:0001", "order_index": 1, "anchor_status": "weak"}],
    }

    row = _page_row_from_outputs(
        payload,
        article_state,
        {},
        {},
        follow_rows=[],
        max_follow_links_per_page=0,
    )

    assert row["page_profile"]["family"] == "biography"
    assert row["dominant_regime"] in {"narrative", "descriptive"}


def test_page_row_from_outputs_reports_mixed_timeline_anchor_honesty() -> None:
    payload = {"title": "Anchor Mix", "links": []}
    article_state = {
        "sentence_units": [
            {"event_id": "art:0001", "text": "On May 5, 2021, Jane arrived.", "anchor_status": "explicit"},
            {"event_id": "art:0002", "text": "In 2021, she worked there.", "anchor_status": "weak"},
            {"event_id": "art:0003", "text": "She later retired.", "anchor_status": "none"},
        ],
        "observations": [{"observation_id": "obs1"}, {"observation_id": "obs2"}, {"observation_id": "obs3"}],
        "event_candidates": [
            {
                "event_id": "art:0001",
                "text": "On May 5, 2021, Jane arrived.",
                "actors": [{"text": "Jane"}],
                "action": "arrive",
                "objects": [],
                "anchor_status": "explicit",
            },
            {
                "event_id": "art:0002",
                "text": "In 2021, she worked there.",
                "actors": [{"text": "Jane"}],
                "action": "work",
                "objects": ["there"],
                "anchor_status": "weak",
            },
            {
                "event_id": "art:0003",
                "text": "She later retired.",
                "actors": [{"text": "Jane"}],
                "action": "retire",
                "objects": [],
                "anchor_status": "none",
            },
        ],
        "timeline_projection": [
            {"event_id": "art:0001", "order_index": 1, "anchor_status": "explicit"},
            {"event_id": "art:0002", "order_index": 2, "anchor_status": "weak"},
            {"event_id": "art:0003", "order_index": 3, "anchor_status": "none"},
        ],
    }

    row = _page_row_from_outputs(
        payload,
        article_state,
        {},
        {},
        follow_rows=[],
        max_follow_links_per_page=0,
    )

    assert row["timeline_honesty"]["explicit_anchor_ratio"] == 0.333333
    assert row["timeline_honesty"]["weak_anchor_ratio"] == 0.333333
    assert row["timeline_honesty"]["none_anchor_ratio"] == 0.333333
    assert row["timeline_honesty"]["timeline_honesty_score"] == 0.5
    assert "timeline_mostly_undated" not in row["honesty_issues"]
    assert "timeline_only_weakly_anchored" not in row["honesty_issues"]


def test_page_row_from_outputs_abstains_when_no_timeline_projection_exists() -> None:
    row = _page_row_from_outputs(
        {"title": "No timeline"},
        {
            "sentence_units": [{"event_id": "art:0001", "text": "Jane patted the cat.", "anchor_status": "none"}],
            "observations": [{"observation_id": "obs1"}],
            "event_candidates": [{"event_id": "art:0001", "text": "Jane patted the cat.", "action": "pat"}],
            "timeline_projection": [],
        },
        {},
        {},
        follow_rows=[],
        max_follow_links_per_page=0,
    )

    assert row["timeline_honesty"]["abstained"] is True
    assert row["timeline_honesty"]["timeline_honesty_score"] is None


def test_build_article_ingest_report_tracks_dominant_regimes_and_follow_yield(tmp_path: Path) -> None:
    first_path = _write_snapshot(
        tmp_path,
        name="first.json",
        title="First example",
        links=["Root link"],
        text=(
            "== Campaign ==\n"
            "Jane performed surgery on the plaintiff in Brisbane.\n"
            "On May 5, 2021, the court ordered damages."
        ),
    )
    second_path = _write_snapshot(
        tmp_path,
        name="second.json",
        title="Second example",
        links=["Compact space"],
        text=(
            "Theorem. Let X be a compact space.\n"
            "There exists a continuous function f."
        ),
    )
    root_link_path = _write_snapshot(
        tmp_path,
        name="root-link.json",
        title="Root link",
        text="Root link is a short descriptive page with enough structure to score.",
    )
    leaf_link_path = _write_snapshot(
        tmp_path,
        name="leaf-link.json",
        title="Leaf link",
        text="Leaf link is another short descriptive page with enough structure to score.",
    )
    manifest = {
        "generated_at": "2026-03-22T00:00:00Z",
        "wiki": "enwiki",
        "requested_count": 2,
        "sampled_count": 2,
        "namespace": 0,
        "follow_hops": 1,
        "max_follow_links_per_page": 2,
        "samples": [
            {
                "snapshot_path": str(first_path),
                "followed_samples": [
                    {
                        "title": "Root link",
                        "snapshot_path": str(root_link_path),
                        "followed_samples": [
                            {"title": "Leaf link", "snapshot_path": str(leaf_link_path)}
                        ],
                    }
                ],
            },
            {"snapshot_path": str(second_path), "followed_samples": []},
        ],
    }

    report = build_article_ingest_report(manifest, emit_page_rows=True, no_spacy=True)

    assert report["summary"]["dominant_regime_counts"]["narrative"] >= 1
    assert report["summary"]["dominant_regime_counts"]["formal"] >= 1
    assert report["summary"]["average_follow_yield_metrics"]["follow_yield_score"] is not None
    assert report["summary"]["average_follow_target_quality"]["overall"] is not None
    assert report["summary"]["average_two_hop_metrics"]["hop1_follow_target_quality"] is not None
    assert report["summary"]["average_best_path_metrics"]["best_path_score"] is not None
    assert report["summary"]["best_path_metrics"]["best_path_score"] is not None
    assert report["pages"][0]["follow_yield_metrics"]["follow_yield_score"] is not None
    assert report["pages"][0]["follow_yield_metrics"]["follow_target_quality_score"] is not None
