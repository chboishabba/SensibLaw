from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from src.wiki_timeline.revision_monitor_query import build_query_payload


def _seed_db(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE wiki_revision_monitor_packs (
          pack_id TEXT PRIMARY KEY,
          version INTEGER,
          scope TEXT,
          manifest_path TEXT NOT NULL,
          manifest_sha256 TEXT NOT NULL,
          manifest_json TEXT NOT NULL,
          updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE wiki_revision_monitor_runs (
          run_id TEXT PRIMARY KEY,
          pack_id TEXT NOT NULL,
          started_at TEXT NOT NULL,
          completed_at TEXT,
          status TEXT NOT NULL,
          out_dir TEXT NOT NULL,
          summary_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE wiki_revision_monitor_articles (
          article_id TEXT PRIMARY KEY,
          pack_id TEXT NOT NULL,
          wiki TEXT NOT NULL,
          title TEXT NOT NULL,
          role TEXT NOT NULL,
          topics_json TEXT NOT NULL,
          review_context_json TEXT NOT NULL,
          article_order INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE wiki_revision_monitor_run_summaries (
          run_id TEXT PRIMARY KEY,
          pack_id TEXT NOT NULL,
          started_at TEXT NOT NULL,
          completed_at TEXT,
          status TEXT NOT NULL,
          out_dir TEXT NOT NULL,
          highest_severity TEXT NOT NULL DEFAULT 'none',
          baseline_initialized_count INTEGER NOT NULL DEFAULT 0,
          unchanged_count INTEGER NOT NULL DEFAULT 0,
          changed_count INTEGER NOT NULL DEFAULT 0,
          error_count INTEGER NOT NULL DEFAULT 0,
          no_candidate_delta_count INTEGER NOT NULL DEFAULT 0,
          candidate_considered_count INTEGER NOT NULL DEFAULT 0,
          candidate_selected_count INTEGER NOT NULL DEFAULT 0,
          candidate_reported_count INTEGER NOT NULL DEFAULT 0,
          graphs_article_count INTEGER NOT NULL DEFAULT 0,
          graphs_built_count INTEGER NOT NULL DEFAULT 0,
          regions_detected_count INTEGER NOT NULL DEFAULT 0,
          cycles_detected_count INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE wiki_revision_monitor_changed_articles (
          run_id TEXT NOT NULL,
          article_id TEXT NOT NULL,
          pack_id TEXT NOT NULL,
          title TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL,
          top_severity TEXT NOT NULL DEFAULT 'none',
          previous_revid INTEGER,
          current_revid INTEGER,
          selected_primary_pair_id TEXT,
          selected_primary_pair_kind TEXT,
          selected_primary_pair_score REAL NOT NULL DEFAULT 0,
          candidate_pairs_selected INTEGER NOT NULL DEFAULT 0,
          report_path TEXT,
          contested_graph_available INTEGER NOT NULL DEFAULT 0,
          contested_graph_path TEXT,
          contested_region_count INTEGER NOT NULL DEFAULT 0,
          contested_cycle_count INTEGER NOT NULL DEFAULT 0,
          graph_heat REAL NOT NULL DEFAULT 0,
          PRIMARY KEY (run_id, article_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE wiki_revision_monitor_issue_packets (
          run_id TEXT NOT NULL,
          article_id TEXT NOT NULL,
          pair_id TEXT NOT NULL,
          packet_id TEXT NOT NULL,
          packet_order INTEGER NOT NULL,
          severity TEXT NOT NULL DEFAULT 'low',
          summary TEXT,
          event_id TEXT,
          surfaces_json TEXT NOT NULL,
          related_entities_json TEXT NOT NULL,
          state_change_summary_json TEXT NOT NULL,
          review_context_json TEXT,
          packet_json TEXT NOT NULL,
          PRIMARY KEY (run_id, article_id, pair_id, packet_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE wiki_revision_monitor_selected_pairs (
          run_id TEXT NOT NULL,
          article_id TEXT NOT NULL,
          pair_id TEXT NOT NULL,
          pair_kind TEXT NOT NULL,
          pair_kinds_json TEXT NOT NULL,
          older_revid INTEGER,
          newer_revid INTEGER,
          candidate_score REAL NOT NULL DEFAULT 0,
          top_severity TEXT NOT NULL DEFAULT 'none',
          pair_report_path TEXT,
          top_changed_sections_json TEXT NOT NULL,
          PRIMARY KEY (run_id, article_id, pair_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE wiki_revision_monitor_contested_graphs (
          run_id TEXT NOT NULL,
          article_id TEXT NOT NULL,
          graph_path TEXT NOT NULL,
          graph_json TEXT NOT NULL,
          region_count INTEGER NOT NULL DEFAULT 0,
          cycle_count INTEGER NOT NULL DEFAULT 0,
          selected_pair_count INTEGER NOT NULL DEFAULT 0,
          changed_event_count INTEGER NOT NULL DEFAULT 0,
          changed_attribution_count INTEGER NOT NULL DEFAULT 0,
          highest_severity TEXT NOT NULL DEFAULT 'none',
          hottest_region_json TEXT,
          PRIMARY KEY (run_id, article_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE wiki_revision_monitor_contested_regions (
          run_id TEXT NOT NULL,
          article_id TEXT NOT NULL,
          region_id TEXT NOT NULL,
          title TEXT NOT NULL,
          touch_count INTEGER NOT NULL DEFAULT 0,
          total_touched_bytes INTEGER NOT NULL DEFAULT 0,
          highest_severity TEXT NOT NULL DEFAULT 'none',
          region_json TEXT NOT NULL,
          PRIMARY KEY (run_id, article_id, region_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE wiki_revision_monitor_contested_cycles (
          run_id TEXT NOT NULL,
          article_id TEXT NOT NULL,
          cycle_id TEXT NOT NULL,
          region_id TEXT NOT NULL,
          touch_count INTEGER NOT NULL DEFAULT 0,
          highest_severity TEXT NOT NULL DEFAULT 'none',
          cycle_json TEXT NOT NULL,
          PRIMARY KEY (run_id, article_id, cycle_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE wiki_revision_monitor_contested_edges (
          run_id TEXT NOT NULL,
          article_id TEXT NOT NULL,
          edge_id TEXT NOT NULL,
          edge_kind TEXT NOT NULL,
          source_id TEXT NOT NULL,
          target_id TEXT NOT NULL,
          edge_json TEXT NOT NULL,
          PRIMARY KEY (run_id, article_id, edge_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE wiki_revision_monitor_contested_events (
          run_id TEXT NOT NULL,
          article_id TEXT NOT NULL,
          event_id TEXT NOT NULL,
          event_json TEXT NOT NULL,
          PRIMARY KEY (run_id, article_id, event_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE wiki_revision_monitor_contested_epistemic (
          run_id TEXT NOT NULL,
          article_id TEXT NOT NULL,
          epistemic_id TEXT NOT NULL,
          epistemic_json TEXT NOT NULL,
          PRIMARY KEY (run_id, article_id, epistemic_id)
        )
        """
    )
    conn.execute(
        "INSERT INTO wiki_revision_monitor_packs(pack_id, version, scope, manifest_path, manifest_sha256, manifest_json, updated_at) VALUES(?,?,?,?,?,?,?)",
        ("pack_one", 1, "test", "manifest.json", "sha", "{}", "2026-03-31T00:00:00Z"),
    )
    conn.execute(
        """
        INSERT INTO wiki_revision_monitor_articles(
          article_id, pack_id, wiki, title, role, topics_json, review_context_json, article_order
        ) VALUES(?,?,?,?,?,?,?,?)
        """,
        ("article_1", "pack_one", "enwiki", "Example Article", "baseline", "[]", "{}", 0),
    )
    summary = {
        "pack_id": "pack_one",
        "run_id": "run:pack_one:2026-03-31T00:00:00Z:abc",
        "articles": [
            {
                "article_id": "article_1",
                "contested_graph_path": None,
            }
        ],
    }
    conn.execute(
        "INSERT INTO wiki_revision_monitor_runs(run_id, pack_id, started_at, completed_at, status, out_dir, summary_json) VALUES(?,?,?,?,?,?,?)",
        (
            "run:pack_one:2026-03-31T00:00:00Z:abc",
            "pack_one",
            "2026-03-31T00:00:00Z",
            "2026-03-31T00:10:00Z",
            "ok",
            "SensibLaw/demo/ingest/wiki_revision_monitor/pack_one",
            json.dumps(summary),
        ),
    )
    conn.execute(
        """
        INSERT INTO wiki_revision_monitor_run_summaries(
          run_id, pack_id, started_at, completed_at, status, out_dir, highest_severity,
          baseline_initialized_count, unchanged_count, changed_count, error_count, no_candidate_delta_count,
          candidate_considered_count, candidate_selected_count, candidate_reported_count,
          graphs_article_count, graphs_built_count, regions_detected_count, cycles_detected_count
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "run:pack_one:2026-03-31T00:00:00Z:abc",
            "pack_one",
            "2026-03-31T00:00:00Z",
            "2026-03-31T00:10:00Z",
            "ok",
            "SensibLaw/demo/ingest/wiki_revision_monitor/pack_one",
            "low",
            0,
            0,
            1,
            0,
            0,
            0,
            0,
            0,
            1,
            1,
            1,
            0,
        ),
    )
    conn.execute(
        """
        INSERT INTO wiki_revision_monitor_changed_articles(
          run_id, article_id, pack_id, title, status, top_severity, previous_revid, current_revid,
          selected_primary_pair_id, selected_primary_pair_kind, selected_primary_pair_score,
          candidate_pairs_selected, report_path, contested_graph_available, contested_graph_path,
          contested_region_count, contested_cycle_count, graph_heat
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "run:pack_one:2026-03-31T00:00:00Z:abc",
            "article_1",
            "pack_one",
            "Example Article",
            "changed",
            "low",
            1,
            2,
            "pair:1",
            "largest_delta_in_window",
            2.5,
            1,
            "/tmp/pair.json",
            1,
            "/tmp/graph.json",
            1,
            0,
            4.0,
        ),
    )
    conn.execute(
        """
        INSERT INTO wiki_revision_monitor_issue_packets(
          run_id, article_id, pair_id, packet_id, packet_order, severity, summary, event_id,
          surfaces_json, related_entities_json, state_change_summary_json, review_context_json, packet_json
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "run:pack_one:2026-03-31T00:00:00Z:abc",
            "article_1",
            "pair:1",
            "packet:1",
            0,
            "high",
            "event text changed",
            "ev:1",
            json.dumps(["narrative"]),
            json.dumps(["Example"]),
            json.dumps(["actors"]),
            json.dumps({"curated": {"curated_qids": ["Q1"]}}),
            json.dumps({"packet_id": "packet:1", "severity": "high"}),
        ),
    )
    conn.execute(
        """
        INSERT INTO wiki_revision_monitor_selected_pairs(
          run_id, article_id, pair_id, pair_kind, pair_kinds_json, older_revid, newer_revid,
          candidate_score, top_severity, pair_report_path, top_changed_sections_json
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "run:pack_one:2026-03-31T00:00:00Z:abc",
            "article_1",
            "pair:1",
            "largest_delta_in_window",
            json.dumps(["largest_delta_in_window"]),
            1,
            2,
            2.5,
            "high",
            "/tmp/pair.json",
            json.dumps([{"section": "History", "touched_bytes": 1200}]),
        ),
    )
    conn.execute(
        "INSERT INTO wiki_revision_monitor_contested_graphs(run_id, article_id, graph_path, graph_json, region_count, cycle_count, selected_pair_count, changed_event_count, changed_attribution_count, highest_severity, hottest_region_json) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (
            "run:pack_one:2026-03-31T00:00:00Z:abc",
            "article_1",
            "/tmp/graph.json",
            json.dumps({"summary": {"region_count": 1}, "article": {"article_id": "article_1"}}),
            1,
            0,
            0,
            0,
            0,
            "low",
            None,
        ),
    )
    conn.execute(
        """
        INSERT INTO wiki_revision_monitor_contested_regions(
          run_id, article_id, region_id, title, touch_count, total_touched_bytes, highest_severity, region_json
        ) VALUES(?,?,?,?,?,?,?,?)
        """,
        (
            "run:pack_one:2026-03-31T00:00:00Z:abc",
            "article_1",
            "region:1",
            "History",
            2,
            1200,
            "high",
            json.dumps(
                {
                    "region_id": "region:1",
                    "title": "History",
                    "touch_count": 2,
                    "total_touched_bytes": 1200,
                    "highest_severity": "high",
                    "graph_heat": 1700.0,
                }
            ),
        ),
    )
    conn.execute(
        """
        INSERT INTO wiki_revision_monitor_contested_cycles(
          run_id, article_id, cycle_id, region_id, touch_count, highest_severity, cycle_json
        ) VALUES(?,?,?,?,?,?,?)
        """,
        (
            "run:pack_one:2026-03-31T00:00:00Z:abc",
            "article_1",
            "cycle:1",
            "region:1",
            2,
            "high",
            json.dumps({"cycle_id": "cycle:1", "region_id": "region:1", "region_title": "History", "touch_count": 2, "highest_severity": "high"}),
        ),
    )
    conn.execute(
        """
        INSERT INTO wiki_revision_monitor_contested_edges(
          run_id, article_id, edge_id, edge_kind, source_id, target_id, edge_json
        ) VALUES(?,?,?,?,?,?,?)
        """,
        (
            "run:pack_one:2026-03-31T00:00:00Z:abc",
            "article_1",
            "edge:1",
            "changes_event",
            "pair:1",
            "ev:1",
            json.dumps({"edge_id": "edge:1", "edge_kind": "changes_event", "source_id": "pair:1", "target_id": "ev:1"}),
        ),
    )
    conn.execute(
        """
        INSERT INTO wiki_revision_monitor_contested_events(
          run_id, article_id, event_id, event_json
        ) VALUES(?,?,?,?)
        """,
        (
            "run:pack_one:2026-03-31T00:00:00Z:abc",
            "article_1",
            "ev:1",
            json.dumps({"event_id": "ev:1"}),
        ),
    )
    conn.execute(
        """
        INSERT INTO wiki_revision_monitor_contested_epistemic(
          run_id, article_id, epistemic_id, epistemic_json
        ) VALUES(?,?,?,?)
        """,
        (
            "run:pack_one:2026-03-31T00:00:00Z:abc",
            "article_1",
            "epi:1",
            json.dumps({"epistemic_id": "epi:1", "event_id": "ev:1"}),
        ),
    )
    conn.commit()
    conn.close()


def test_revision_monitor_query_reads_db_backed_summary_and_graph(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / "SensibLaw").mkdir(parents=True)
    db_path = repo_root / "SensibLaw" / ".cache_local" / "wiki.sqlite"
    db_path.parent.mkdir(parents=True)
    _seed_db(db_path)

    payload = build_query_payload(db_path=db_path, pack_id="pack_one", run_id="run:pack_one:2026-03-31T00:00:00Z:abc", article_id="article_1")

    assert payload["selected_pack_id"] == "pack_one"
    assert payload["selected_run_id"] == "run:pack_one:2026-03-31T00:00:00Z:abc"
    assert payload["summary"]["pack_id"] == "pack_one"
    assert payload["summary_source"] == "sqlite_read_model"
    assert payload["latest_runs"][0]["run_id"] == "run:pack_one:2026-03-31T00:00:00Z:abc"
    assert payload["changed_articles"][0]["article_id"] == "article_1"
    assert payload["selected_pairs"][0]["pair_id"] == "pair:1"
    assert payload["selected_pairs"][0]["top_changed_sections"][0]["section"] == "History"
    assert payload["selected_issue_packets"][0]["packet_id"] == "packet:1"
    assert payload["selected_issue_packets"][0]["review_context"]["curated"]["curated_qids"] == ["Q1"]
    assert payload["selected_graph"]["article"]["article_id"] == "article_1"
    assert payload["selected_graph_source"] == "sqlite_read_model"
    assert payload["selected_graph"]["regions"][0]["region_id"] == "region:1"
    assert payload["selected_graph"]["events"][0]["event_id"] == "ev:1"
    assert payload["selected_graph"]["epistemic_surfaces"][0]["epistemic_id"] == "epi:1"


def test_revision_monitor_query_prefers_sqlite_read_models_over_blob_columns(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / "SensibLaw").mkdir(parents=True)
    db_path = repo_root / "SensibLaw" / ".cache_local" / "wiki.sqlite"
    db_path.parent.mkdir(parents=True)
    _seed_db(db_path)

    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE wiki_revision_monitor_runs SET summary_json = ? WHERE run_id = ?",
        (
            json.dumps({"pack_id": "pack_one", "run_id": "run:pack_one:2026-03-31T00:00:00Z:abc", "articles": [{"article_id": "wrong_article"}]}),
            "run:pack_one:2026-03-31T00:00:00Z:abc",
        ),
    )
    conn.execute(
        "UPDATE wiki_revision_monitor_contested_graphs SET graph_json = ? WHERE run_id = ? AND article_id = ?",
        (
            json.dumps({"article": {"article_id": "wrong_article"}, "summary": {"region_count": 999}}),
            "run:pack_one:2026-03-31T00:00:00Z:abc",
            "article_1",
        ),
    )
    conn.commit()
    conn.close()

    payload = build_query_payload(db_path=db_path, pack_id="pack_one", run_id="run:pack_one:2026-03-31T00:00:00Z:abc", article_id="article_1")

    assert payload["summary_source"] == "sqlite_read_model"
    assert payload["summary"]["pack_triage"]["top_changed_articles"][0]["article_id"] == "article_1"
    assert payload["selected_graph_source"] == "sqlite_read_model"
    assert payload["selected_graph"]["article"]["article_id"] == "article_1"


def test_query_script_imports_shared_query_owner() -> None:
    source = (Path(__file__).resolve().parents[1] / "scripts" / "query_wiki_revision_monitor.py").read_text(encoding="utf-8")
    assert "from src.wiki_timeline.revision_monitor_query import build_query_payload" in source
    assert "payload = build_query_payload(" in source
