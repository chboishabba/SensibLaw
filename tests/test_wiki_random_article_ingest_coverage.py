from __future__ import annotations

import json
from pathlib import Path

from scripts.report_wiki_random_article_ingest_coverage import (
    _event_has_action,
    _event_has_object,
    _page_row_from_outputs,
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


def test_score_snapshot_payload_reports_canonical_state_and_follow_usage() -> None:
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
        follow_rows=[{"title": "Cat"}],
        max_follow_links_per_page=2,
        no_spacy=True,
    )

    assert row["article_sentence_count"] >= 2
    assert row["observation_count"] >= row["article_aao_event_count"]
    assert row["article_aao_event_count"] >= 1
    assert row["action_event_count"] >= 1
    assert row["followed_snapshot_count"] == 1
    assert row["scores"]["article_ingest_score"] > 0.0
    assert row["scores"]["observation_density_score"] > 0.0
    assert row["timeline_projection"]["event_count"] == row["article_aao_event_count"]
    assert "none" in row["timeline_projection"]["anchor_status_counts"] or "explicit" in row["timeline_projection"]["anchor_status_counts"]
    assert row["timeline_readiness"]["scores"]["overall_readiness_score"] > 0.0


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
            {"snapshot_path": str(strong_path), "followed_samples": [{"title": "Cat"}]},
            {"snapshot_path": str(weak_path), "followed_samples": []},
        ],
    }

    report = build_article_ingest_report(manifest, emit_page_rows=True, no_spacy=True)
    assert report["schema_version"] == "wiki_random_article_ingest_coverage_report_v0_1"
    assert report["supported_surface"]["canonical_state_surface"] == "wiki_article_state_v0_1"
    assert report["summary"]["page_count"] == 2
    assert report["summary"]["pages_with_article_sentences"] == 2
    assert report["summary"]["pages_with_article_aao_events"] >= 1
    assert report["summary"]["pages_with_followed_snapshots"] == 1
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
                        "followed_samples": [{"title": "Cat"}],
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
