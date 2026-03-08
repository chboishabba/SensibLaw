from __future__ import annotations

import json
import sqlite3
import subprocess
from pathlib import Path

from src.wiki_timeline.revision_pack_runner import default_out_dir_for_pack, human_summary, run


def _pack(tmp_path: Path) -> Path:
    payload = {
        "pack_id": "test_pack",
        "version": 1,
        "scope": "test",
        "provenance": {"created_on": "2026-03-09"},
        "articles": [
            {
                "article_id": "article_1",
                "wiki": "enwiki",
                "title": "Example Article",
                "role": "baseline",
                "topics": ["baseline"],
                "review_context": {"curated_qids": ["Q1"], "diagnostic_topics": ["baseline"]},
            }
        ],
    }
    path = tmp_path / "pack.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _snapshot_payload(revid: int) -> dict:
    return {
        "wiki": "enwiki",
        "title": "Example Article",
        "revid": revid,
        "rev_timestamp": f"2026-03-09T00:00:{revid:02d}Z",
        "fetched_at": f"2026-03-09T00:01:{revid:02d}Z",
        "source_url": "https://en.wikipedia.org/wiki/Example_Article",
        "wikitext": f"Revision {revid} text",
    }


def _timeline_payload(revid: int) -> dict:
    return {
        "snapshot": _snapshot_payload(revid),
        "events": [
            {
                "event_id": "ev:0001",
                "anchor": {"year": 2026, "precision": "year", "text": "2026", "kind": "explicit"},
                "section": "History",
                "text": f"Event for revision {revid}",
                "links": ["Example"],
                "links_para": ["Example"],
            }
        ],
    }


def _aoo_payload(revid: int) -> dict:
    claim_bearing = revid >= 2
    return {
        "source_timeline": {"path": f"/tmp/timeline_{revid}.json", "snapshot": _snapshot_payload(revid)},
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


def test_pack_runner_baseline_unchanged_changed_cycle(tmp_path: Path) -> None:
    pack_path = _pack(tmp_path)
    out_dir = tmp_path / "out"
    state_db = tmp_path / "state.sqlite"
    current_revid = {"value": 1}

    def fake_fetch_current_snapshot_fn(*, article, out_dir, python_cmd, repo_root):
        payload = _snapshot_payload(current_revid["value"])
        path = out_dir / f"{article['article_id']}_{current_revid['value']}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
        return {"snapshot_path": path, "snapshot_payload": payload}

    def fake_build_timeline_fn(*, snapshot_path, out_path, python_cmd, repo_root):
        revid = int(json.loads(snapshot_path.read_text(encoding="utf-8"))["revid"])
        payload = _timeline_payload(revid)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload), encoding="utf-8")
        return {"timeline_path": out_path, "timeline_payload": payload}

    def fake_build_aoo_fn(*, article, timeline_path, out_path, python_cmd, repo_root):
        revid = int(json.loads(timeline_path.read_text(encoding="utf-8"))["snapshot"]["revid"])
        payload = _aoo_payload(revid)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload), encoding="utf-8")
        return {"aoo_path": out_path, "aoo_payload": payload}

    def fake_auto_review_context_fn(*, packet, article, bridge_db_path):
        return {"auto_bridge_matches": [{"curie": "wikidata:Q1065", "source_surface": "United Nations"}]}

    first = run(
        pack_path=pack_path,
        out_dir=out_dir,
        state_db_path=state_db,
        fetch_current_snapshot_fn=fake_fetch_current_snapshot_fn,
        build_timeline_fn=fake_build_timeline_fn,
        build_aoo_fn=fake_build_aoo_fn,
        auto_review_context_fn=fake_auto_review_context_fn,
    )
    assert first["counts"]["baseline_initialized"] == 1
    assert first["counts"]["changed"] == 0

    second = run(
        pack_path=pack_path,
        out_dir=out_dir,
        state_db_path=state_db,
        fetch_current_snapshot_fn=fake_fetch_current_snapshot_fn,
        build_timeline_fn=fake_build_timeline_fn,
        build_aoo_fn=fake_build_aoo_fn,
        auto_review_context_fn=fake_auto_review_context_fn,
    )
    assert second["counts"]["unchanged"] == 1

    current_revid["value"] = 2
    third = run(
        pack_path=pack_path,
        out_dir=out_dir,
        state_db_path=state_db,
        fetch_current_snapshot_fn=fake_fetch_current_snapshot_fn,
        build_timeline_fn=fake_build_timeline_fn,
        build_aoo_fn=fake_build_aoo_fn,
        auto_review_context_fn=fake_auto_review_context_fn,
    )
    assert third["counts"]["changed"] == 1
    assert third["highest_severity"] == "high"
    report_path = Path(third["articles"][0]["report_path"])
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["issue_packets"][0]["review_context"]["curated"]["curated_qids"] == ["Q1"]
    assert report["issue_packets"][0]["review_context"]["auto_bridge_matches"][0]["curie"] == "wikidata:Q1065"

    with sqlite3.connect(state_db) as conn:
        conn.row_factory = sqlite3.Row
        state = conn.execute("SELECT last_revid, status FROM wiki_revision_monitor_article_state WHERE article_id = 'article_1'").fetchone()
        assert state["last_revid"] == 2
        assert state["status"] == "changed"


def test_pack_runner_records_error_without_state_corruption(tmp_path: Path) -> None:
    pack_path = _pack(tmp_path)
    out_dir = tmp_path / "out"
    state_db = tmp_path / "state.sqlite"

    def ok_fetch(*, article, out_dir, python_cmd, repo_root):
        payload = _snapshot_payload(1)
        path = out_dir / "ok.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
        return {"snapshot_path": path, "snapshot_payload": payload}

    def ok_timeline(*, snapshot_path, out_path, python_cmd, repo_root):
        payload = _timeline_payload(1)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload), encoding="utf-8")
        return {"timeline_path": out_path, "timeline_payload": payload}

    def ok_aoo(*, article, timeline_path, out_path, python_cmd, repo_root):
        payload = _aoo_payload(1)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload), encoding="utf-8")
        return {"aoo_path": out_path, "aoo_payload": payload}

    run(
        pack_path=pack_path,
        out_dir=out_dir,
        state_db_path=state_db,
        fetch_current_snapshot_fn=ok_fetch,
        build_timeline_fn=ok_timeline,
        build_aoo_fn=ok_aoo,
        auto_review_context_fn=lambda **_: {},
    )

    def bad_fetch(*, article, out_dir, python_cmd, repo_root):
        raise RuntimeError("network unhappy")

    result = run(
        pack_path=pack_path,
        out_dir=out_dir,
        state_db_path=state_db,
        fetch_current_snapshot_fn=bad_fetch,
        build_timeline_fn=ok_timeline,
        build_aoo_fn=ok_aoo,
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


def test_pack_runner_cli_human_summary(tmp_path: Path) -> None:
    payload = {
        "pack_id": "pack",
        "run_id": "run:1",
        "counts": {"baseline_initialized": 1, "unchanged": 0, "changed": 0, "error": 0},
        "highest_severity": "none",
        "articles": [{"article_id": "article_1", "status": "baseline_initialized", "previous_revid": None, "current_revid": 1, "report_path": None}],
    }
    text = human_summary(payload)
    assert "pack=pack run=run:1" in text
    assert "baseline_initialized=1" in text

    script = Path(__file__).resolve().parents[1] / "scripts" / "wiki_revision_pack_runner.py"
    completed = subprocess.run(
        ["python", str(script), "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "--summary-format" in completed.stdout
