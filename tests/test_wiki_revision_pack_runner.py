from __future__ import annotations

import json
import sqlite3
import subprocess
from pathlib import Path

from src.wiki_timeline.revision_pack_runner import default_out_dir_for_pack, human_summary, run


def _pack(tmp_path: Path, *, pack_id: str = "test_pack") -> Path:
    payload = {
        "pack_id": pack_id,
        "version": 1,
        "scope": "test",
        "provenance": {"created_on": "2026-03-09"},
        "history_defaults": {
            "max_revisions": 5,
            "window_days": 14,
            "max_candidate_pairs": 2,
            "section_focus_limit": 3,
        },
        "graph_enabled": True,
        "articles": [
            {
                "article_id": "article_1",
                "wiki": "enwiki",
                "title": "Example Article",
                "role": "baseline",
                "graph_enabled": True,
                "topics": ["baseline"],
                "review_context": {"curated_qids": ["Q1"], "diagnostic_topics": ["baseline"]},
            }
        ],
    }
    path = tmp_path / "pack.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _snapshot_payload(revid: int, *, body: str | None = None) -> dict:
    if body is None:
        body = (
            "Intro text.\n"
            "== History ==\n"
            f"Revision {revid} history.\n"
            "== Legacy ==\n"
            f"Legacy section {revid}.\n"
        )
    return {
        "wiki": "enwiki",
        "title": "Example Article",
        "revid": revid,
        "rev_timestamp": f"2026-03-09T00:00:{revid:02d}Z",
        "fetched_at": f"2026-03-09T00:01:{revid:02d}Z",
        "source_url": "https://en.wikipedia.org/wiki/Example_Article",
        "wikitext": body,
    }


def _timeline_payload(snapshot_payload: dict) -> dict:
    revid = int(snapshot_payload["revid"])
    section = "History" if "History" in snapshot_payload["wikitext"] else "Legacy"
    return {
        "snapshot": snapshot_payload,
        "events": [
            {
                "event_id": "ev:0001",
                "anchor": {"year": 2026, "precision": "year", "text": "2026", "kind": "explicit"},
                "section": section,
                "text": f"Event for revision {revid}",
                "links": ["Example"],
                "links_para": ["Example"],
            }
        ],
    }


def _aoo_payload(snapshot_payload: dict) -> dict:
    revid = int(snapshot_payload["revid"])
    claim_bearing = revid >= 2
    return {
        "source_timeline": {"path": f"/tmp/timeline_{revid}.json", "snapshot": snapshot_payload},
        "source_entity": {
            "id": "source:test",
            "type": "wikipedia_article",
            "title": "Example Article",
            "url": "https://en.wikipedia.org/wiki/Example_Article",
            "version_hash": str(revid),
        },
        "events": [
            {
                "event_id": "ev:0001",
                "text": f"Event for revision {revid}",
                "action": "report" if claim_bearing else "meet",
                "actors": [{"label": "United Nations"}],
                "objects": [{"title": "Example"}],
                "steps": [
                    {
                        "action": "report" if claim_bearing else "meet",
                        "subjects": ["United Nations"],
                        "objects": [{"title": "Example"}],
                        "claim_bearing": claim_bearing,
                    }
                ],
                "claim_bearing": claim_bearing,
                "claim_step_indices": [0] if claim_bearing else [],
                "attributions": (
                    [{"attributed_actor_id": "United Nations", "attribution_type": "direct_statement", "step_index": 0}]
                    if claim_bearing
                    else []
                ),
            }
        ],
    }


def _history_rows(*revids: int) -> list[dict]:
    rows = []
    for revid in sorted(revids, reverse=True):
        rows.append(
            {
                "revid": revid,
                "parentid": revid - 1 if revid > 1 else None,
                "timestamp": f"2026-03-09T00:00:{revid:02d}Z",
                "size": 100 + (revid * 50),
                "comment": "reverted vandalism" if revid == 2 else f"edit {revid}",
                "user": "tester",
                "anon": False,
            }
        )
    return rows


def _fake_env(tmp_path: Path, current_revid_box: dict[str, int]):
    snapshot_store = {
        1: _snapshot_payload(1, body="Intro text.\n== History ==\nSmall change.\n== Legacy ==\nalpha.\n"),
        2: _snapshot_payload(2, body="Intro text updated.\n== History ==\nMajor revision with much larger section text here.\n== Legacy ==\nbeta.\n"),
        3: _snapshot_payload(3, body="Intro text updated.\n== History ==\nMajor revision with much larger section text here and follow-up.\n== Legacy ==\ngamma.\n"),
    }

    def fetch_current(*, article, out_dir, python_cmd, repo_root):
        payload = snapshot_store[current_revid_box["value"]]
        path = out_dir / f"current_{payload['revid']}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
        return {"snapshot_path": path, "snapshot_payload": payload}

    def fetch_revision(*, article, revid, out_dir, python_cmd, repo_root):
        payload = snapshot_store[int(revid)]
        path = out_dir / f"revid_{revid}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
        return {"snapshot_path": path, "snapshot_payload": payload}

    def fetch_history(*, article, out_dir, python_cmd, repo_root, max_revisions, window_days):
        payload = {
            "title": article["title"],
            "rows": _history_rows(3, 2, 1)[:max_revisions],
            "max_revisions": max_revisions,
            "window_days": window_days,
        }
        path = out_dir / "history.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
        return {"history_path": path, "history_payload": payload}

    def build_timeline(*, snapshot_path, out_path, python_cmd, repo_root):
        snapshot_payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
        payload = _timeline_payload(snapshot_payload)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload), encoding="utf-8")
        return {"timeline_path": out_path, "timeline_payload": payload}

    def build_aoo(*, article, timeline_path, out_path, python_cmd, repo_root):
        timeline_payload = json.loads(timeline_path.read_text(encoding="utf-8"))
        payload = _aoo_payload(timeline_payload["snapshot"])
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload), encoding="utf-8")
        return {"aoo_path": out_path, "aoo_payload": payload}

    def auto_review_context(*, packet, article, bridge_db_path):
        return {"auto_bridge_matches": [{"curie": "wikidata:Q1065", "source_surface": "United Nations"}]}

    return fetch_current, fetch_revision, fetch_history, build_timeline, build_aoo, auto_review_context


def test_pack_runner_history_pairs_and_state_cycle(tmp_path: Path) -> None:
    pack_path = _pack(tmp_path)
    out_dir = tmp_path / "out"
    state_db = tmp_path / "state.sqlite"
    current_revid = {"value": 1}
    fetch_current, fetch_revision, fetch_history, build_timeline, build_aoo, auto_review_context = _fake_env(tmp_path, current_revid)

    first = run(
        pack_path=pack_path,
        out_dir=out_dir,
        state_db_path=state_db,
        fetch_current_snapshot_fn=fetch_current,
        fetch_revision_history_fn=fetch_history,
        fetch_revision_snapshot_fn=fetch_revision,
        build_timeline_fn=build_timeline,
        build_aoo_fn=build_aoo,
        auto_review_context_fn=auto_review_context,
    )
    assert first["counts"]["changed"] == 1
    assert first["candidate_pair_counts"]["reported"] >= 1
    assert first["articles"][0]["baseline_initialized"] is True
    assert first["articles"][0]["candidate_pairs_selected"] >= 1
    first_report = Path(first["articles"][0]["pair_reports"][0]["pair_report_path"])
    pair_report = json.loads(first_report.read_text(encoding="utf-8"))
    assert pair_report["schema_version"] == "wiki_revision_pair_report_v0_1"
    assert pair_report["highest_severity"] in {"high", "medium", "low", "none"}
    assert isinstance(pair_report["packet_counts"], dict)
    assert pair_report["section_delta_summary"]["changed_section_count"] >= 1
    assert pair_report["comparison_report"]["issue_packets"][0]["review_context"]["curated"]["curated_qids"] == ["Q1"]
    assert pair_report["comparison_report"]["issue_packets"][0]["review_context"]["auto_bridge_matches"][0]["curie"] == "wikidata:Q1065"
    assert "section_context" in pair_report["comparison_report"]["issue_packets"][0]
    assert first["articles"][0]["selected_primary_pair_kind"] is not None
    assert first["articles"][0]["selected_primary_pair_id"] is not None
    assert first["articles"][0]["selected_primary_pair_score"] is not None
    assert isinstance(first["articles"][0]["packet_counts"], dict)
    assert first["articles"][0]["contested_graph_available"] is True
    assert first["articles"][0]["contested_graph_path"]
    assert first["articles"][0]["contested_graph_summary"]["region_count"] >= 1
    assert first["pack_triage"]["top_changed_articles"][0]["article_id"] == "article_1"
    assert first["pack_triage"]["top_high_severity_pairs"][0]["article_id"] == "article_1"
    assert first["pack_triage"]["top_sections_changed"][0]["section"] in {"History", "Legacy", "(lead)"}
    assert first["pack_triage"]["top_contested_graphs"][0]["article_id"] == "article_1"
    assert first["pack_triage"]["top_contested_regions"][0]["article_id"] == "article_1"

    second = run(
        pack_path=pack_path,
        out_dir=out_dir,
        state_db_path=state_db,
        fetch_current_snapshot_fn=fetch_current,
        fetch_revision_history_fn=fetch_history,
        fetch_revision_snapshot_fn=fetch_revision,
        build_timeline_fn=build_timeline,
        build_aoo_fn=build_aoo,
        auto_review_context_fn=auto_review_context,
    )
    assert second["counts"]["changed"] == 1
    assert second["articles"][0]["previous_revid"] == 1

    current_revid["value"] = 3
    third = run(
        pack_path=pack_path,
        out_dir=out_dir,
        state_db_path=state_db,
        fetch_current_snapshot_fn=fetch_current,
        fetch_revision_history_fn=fetch_history,
        fetch_revision_snapshot_fn=fetch_revision,
        build_timeline_fn=build_timeline,
        build_aoo_fn=build_aoo,
        auto_review_context_fn=auto_review_context,
    )
    assert third["counts"]["changed"] == 1
    assert third["highest_severity"] == "high"
    with sqlite3.connect(state_db) as conn:
        conn.row_factory = sqlite3.Row
        state = conn.execute("SELECT last_revid, status FROM wiki_revision_monitor_article_state WHERE article_id = 'article_1'").fetchone()
        assert state["last_revid"] == 3
        pair_rows = conn.execute("SELECT count(*) FROM wiki_revision_monitor_candidate_pairs WHERE article_id = 'article_1'").fetchone()
        assert pair_rows[0] >= 2
        graph_rows = conn.execute("SELECT count(*) FROM wiki_revision_monitor_contested_graphs WHERE article_id = 'article_1'").fetchone()
        assert graph_rows[0] >= 1


def test_pack_runner_emits_progress(tmp_path: Path) -> None:
    pack_path = _pack(tmp_path)
    out_dir = tmp_path / "out"
    state_db = tmp_path / "state.sqlite"
    current_revid = {"value": 1}
    fetch_current, fetch_revision, fetch_history, build_timeline, build_aoo, auto_review_context = _fake_env(tmp_path, current_revid)
    seen: list[tuple[str, dict]] = []

    result = run(
        pack_path=pack_path,
        out_dir=out_dir,
        state_db_path=state_db,
        fetch_current_snapshot_fn=fetch_current,
        fetch_revision_history_fn=fetch_history,
        fetch_revision_snapshot_fn=fetch_revision,
        build_timeline_fn=build_timeline,
        build_aoo_fn=build_aoo,
        auto_review_context_fn=auto_review_context,
        progress_callback=lambda stage, details: seen.append((stage, details)),
    )

    assert result["ok"] is True
    stages = [stage for stage, _ in seen]
    assert "revision_pack_articles_started" in stages
    assert "revision_pack_article_started" in stages
    assert "revision_pack_article_history" in stages
    assert "revision_pack_article_candidates_progress" in stages
    assert "revision_pack_article_reports_progress" in stages
    finished = [details for stage, details in seen if stage == "revision_pack_article_finished"]
    assert finished[-1]["status"] == "changed"


def test_pack_runner_records_error_without_state_corruption(tmp_path: Path) -> None:
    pack_path = _pack(tmp_path)
    out_dir = tmp_path / "out"
    state_db = tmp_path / "state.sqlite"
    current_revid = {"value": 1}
    fetch_current, fetch_revision, fetch_history, build_timeline, build_aoo, auto_review_context = _fake_env(tmp_path, current_revid)

    run(
        pack_path=pack_path,
        out_dir=out_dir,
        state_db_path=state_db,
        fetch_current_snapshot_fn=fetch_current,
        fetch_revision_history_fn=fetch_history,
        fetch_revision_snapshot_fn=fetch_revision,
        build_timeline_fn=build_timeline,
        build_aoo_fn=build_aoo,
        auto_review_context_fn=auto_review_context,
    )

    def bad_fetch(*, article, out_dir, python_cmd, repo_root):
        raise RuntimeError("network unhappy")

    result = run(
        pack_path=pack_path,
        out_dir=out_dir,
        state_db_path=state_db,
        fetch_current_snapshot_fn=bad_fetch,
        fetch_revision_history_fn=fetch_history,
        fetch_revision_snapshot_fn=fetch_revision,
        build_timeline_fn=build_timeline,
        build_aoo_fn=build_aoo,
        auto_review_context_fn=lambda **_: {},
    )
    assert result["counts"]["error"] == 1
    with sqlite3.connect(state_db) as conn:
        conn.row_factory = sqlite3.Row
        state = conn.execute("SELECT last_revid FROM wiki_revision_monitor_article_state WHERE article_id = 'article_1'").fetchone()
        assert state["last_revid"] == 1


def test_pack_runner_rejects_incomplete_snapshot_payload(tmp_path: Path) -> None:
    pack_path = _pack(tmp_path)
    out_dir = tmp_path / "out"
    state_db = tmp_path / "state.sqlite"
    _, fetch_revision, fetch_history, build_timeline, build_aoo, _ = _fake_env(tmp_path, {"value": 1})

    def incomplete_fetch(*, article, out_dir, python_cmd, repo_root):
        payload = {
            "wiki": "enwiki",
            "title": article["title"],
            "revid": None,
            "rev_timestamp": None,
            "fetched_at": "2026-03-09T00:01:00Z",
            "wikitext": None,
            "warnings": ["page_missing", "no_revisions_returned"],
        }
        path = out_dir / "bad.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
        return {"snapshot_path": path, "snapshot_payload": payload}

    result = run(
        pack_path=pack_path,
        out_dir=out_dir,
        state_db_path=state_db,
        fetch_current_snapshot_fn=incomplete_fetch,
        fetch_revision_history_fn=fetch_history,
        fetch_revision_snapshot_fn=fetch_revision,
        build_timeline_fn=lambda **_: (_ for _ in ()).throw(AssertionError("timeline should not run")),
        build_aoo_fn=lambda **_: (_ for _ in ()).throw(AssertionError("aoo should not run")),
        auto_review_context_fn=lambda **_: {},
    )
    assert result["counts"]["error"] == 1
    assert "incomplete snapshot" in result["articles"][0]["error"]
    with sqlite3.connect(state_db) as conn:
        state = conn.execute("SELECT count(*) FROM wiki_revision_monitor_article_state").fetchone()
        assert state[0] == 0


def test_default_out_dir_for_pack_uses_pack_id(tmp_path: Path) -> None:
    pack_path = _pack(tmp_path)
    assert default_out_dir_for_pack(pack_path) == Path("SensibLaw/demo/ingest/wiki_revision_monitor/test_pack")


def test_pack_runner_allows_same_article_ids_across_packs(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    state_db = tmp_path / "state.sqlite"
    current_revid = {"value": 1}
    fetch_current, fetch_revision, fetch_history, build_timeline, build_aoo, auto_review_context = _fake_env(tmp_path, current_revid)

    first_pack = _pack(tmp_path / "p1", pack_id="pack_one")
    second_pack = _pack(tmp_path / "p2", pack_id="pack_two")

    first = run(
        pack_path=first_pack,
        out_dir=out_dir / "one",
        state_db_path=state_db,
        fetch_current_snapshot_fn=fetch_current,
        fetch_revision_history_fn=fetch_history,
        fetch_revision_snapshot_fn=fetch_revision,
        build_timeline_fn=build_timeline,
        build_aoo_fn=build_aoo,
        auto_review_context_fn=auto_review_context,
    )
    second = run(
        pack_path=second_pack,
        out_dir=out_dir / "two",
        state_db_path=state_db,
        fetch_current_snapshot_fn=fetch_current,
        fetch_revision_history_fn=fetch_history,
        fetch_revision_snapshot_fn=fetch_revision,
        build_timeline_fn=build_timeline,
        build_aoo_fn=build_aoo,
        auto_review_context_fn=auto_review_context,
    )

    assert first["ok"] is True
    assert second["ok"] is True
    with sqlite3.connect(state_db) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT pack_id FROM wiki_revision_monitor_articles WHERE article_id = 'article_1'").fetchone()
        assert row["pack_id"] == "pack_two"


def test_pack_runner_cli_human_summary(tmp_path: Path) -> None:
    payload = {
        "pack_id": "pack",
        "run_id": "run:1",
        "counts": {"baseline_initialized": 0, "unchanged": 0, "changed": 1, "no_candidate_delta": 0, "error": 0},
        "candidate_pair_counts": {"considered": 3, "selected": 2, "reported": 2},
        "contested_graph_counts": {"articles_with_graphs": 1, "graphs_built": 1, "regions_detected": 4, "cycles_detected": 2},
        "highest_severity": "high",
        "pack_triage": {
            "top_changed_articles": [
                {
                    "article_id": "article_1",
                    "top_severity": "high",
                    "selected_primary_pair_kind": "largest_delta_in_window",
                }
            ],
            "top_high_severity_pairs": [
                {
                    "article_id": "article_1",
                    "pair_kind": "largest_delta_in_window",
                    "top_severity": "high",
                }
            ],
            "top_sections_changed": [
                {
                    "section": "History",
                    "max_touched_bytes": 1200,
                }
            ],
            "top_contested_graphs": [
                {
                    "article_id": "article_1",
                    "graph_heat": 888.0,
                }
            ],
            "top_contested_cycles": [
                {
                    "article_id": "article_1",
                    "region_title": "History",
                }
            ],
            "top_contested_regions": [
                {
                    "article_id": "article_1",
                    "region_title": "History",
                }
            ],
        },
        "articles": [
            {
                "article_id": "article_1",
                "status": "changed",
                "top_severity": "high",
                "previous_revid": 1,
                "current_revid": 2,
                "selected_primary_pair_kind": "largest_delta_in_window",
                "candidate_pairs_selected": 2,
                "report_path": "/tmp/pair.json",
            }
        ],
    }
    text = human_summary(payload)
    assert "pack=pack run=run:1" in text
    assert "pairs: considered=3 selected=2 reported=2" in text
    assert "graphs: articles=1 built=1 regions=4 cycles=2" in text
    assert "top_articles=article_1:high:largest_delta_in_window" in text
    assert "top_pairs=article_1:largest_delta_in_window:high" in text
    assert "top_sections=History:1200" in text
    assert "article_1: status=changed sev=high prev=1 curr=2 primary_pair=largest_delta_in_window pairs=2 report=/tmp/pair.json" in text

    script = Path(__file__).resolve().parents[1] / "scripts" / "wiki_revision_pack_runner.py"
    completed = subprocess.run(
        ["python", str(script), "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "--summary-format" in completed.stdout
