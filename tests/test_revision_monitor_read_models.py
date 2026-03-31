from __future__ import annotations

import sqlite3

from src.wiki_timeline.revision_monitor_read_models import (
    changed_article_rows,
    contested_graph_payload,
    ensure_read_model_schema,
    issue_packet_rows,
    latest_run_rows,
    replace_changed_articles,
    replace_issue_packets,
    replace_selected_pairs,
    selected_pair_rows,
    summary_from_read_models,
    upsert_run_summary,
)


def test_revision_monitor_read_models_round_trip() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("CREATE TABLE wiki_revision_monitor_packs (pack_id TEXT PRIMARY KEY)")
    conn.execute("CREATE TABLE wiki_revision_monitor_runs (run_id TEXT PRIMARY KEY, pack_id TEXT NOT NULL REFERENCES wiki_revision_monitor_packs(pack_id) ON DELETE CASCADE)")
    conn.execute(
        """
        CREATE TABLE wiki_revision_monitor_articles (
          article_id TEXT PRIMARY KEY,
          pack_id TEXT NOT NULL REFERENCES wiki_revision_monitor_packs(pack_id) ON DELETE CASCADE
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
    ensure_read_model_schema(conn)
    conn.execute("INSERT INTO wiki_revision_monitor_packs(pack_id) VALUES('pack_one')")
    conn.execute("INSERT INTO wiki_revision_monitor_runs(run_id, pack_id) VALUES('run:pack_one:2026-03-31T00:00:00Z:abc', 'pack_one')")
    conn.executemany(
        "INSERT INTO wiki_revision_monitor_articles(article_id, pack_id) VALUES(?, 'pack_one')",
        [("article_1",), ("article_2",)],
    )

    upsert_run_summary(
        conn,
        run_id="run:pack_one:2026-03-31T00:00:00Z:abc",
        pack_id="pack_one",
        started_at="2026-03-31T00:00:00Z",
        completed_at="2026-03-31T00:10:00Z",
        status="ok",
        out_dir="SensibLaw/demo/ingest/wiki_revision_monitor/pack_one",
        summary={
            "highest_severity": "high",
            "counts": {"changed": 2, "error": 0, "unchanged": 0, "baseline_initialized": 0, "no_candidate_delta": 0},
            "candidate_pair_counts": {"considered": 4, "selected": 2, "reported": 2},
            "contested_graph_counts": {"articles_with_graphs": 1, "graphs_built": 1, "regions_detected": 3, "cycles_detected": 1},
        },
    )
    replace_changed_articles(
        conn,
        run_id="run:pack_one:2026-03-31T00:00:00Z:abc",
        pack_id="pack_one",
        article_rows=[
            {
                "article_id": "article_2",
                "title": "Second",
                "status": "changed",
                "top_severity": "medium",
                "selected_primary_pair_score": 2.0,
                "candidate_pairs_selected": 1,
            },
            {
                "article_id": "article_1",
                "title": "First",
                "status": "changed",
                "top_severity": "high",
                "selected_primary_pair_kind": "largest_delta_in_window",
                "selected_primary_pair_score": 9.5,
                "candidate_pairs_selected": 2,
                "contested_graph_available": True,
                "contested_graph_path": "/tmp/graph.json",
                "contested_graph_summary": {"region_count": 3, "cycle_count": 1, "graph_heat": 7.5},
            },
        ],
    )

    latest = latest_run_rows(conn, pack_id="pack_one")
    changed = changed_article_rows(conn, run_id="run:pack_one:2026-03-31T00:00:00Z:abc")
    summary = summary_from_read_models(conn, run_id="run:pack_one:2026-03-31T00:00:00Z:abc")

    assert latest[0]["highest_severity"] == "high"
    assert changed[0]["article_id"] == "article_1"
    assert changed[0]["contested_graph_available"] is True
    assert summary is not None
    assert summary["pack_id"] == "pack_one"
    assert summary["counts"]["changed"] == 2
    assert summary["pack_triage"]["top_changed_articles"][0]["article_id"] == "article_1"


def test_revision_monitor_issue_packet_rows_round_trip() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("CREATE TABLE wiki_revision_monitor_packs (pack_id TEXT PRIMARY KEY)")
    conn.execute("CREATE TABLE wiki_revision_monitor_runs (run_id TEXT PRIMARY KEY, pack_id TEXT NOT NULL REFERENCES wiki_revision_monitor_packs(pack_id) ON DELETE CASCADE)")
    conn.execute(
        """
        CREATE TABLE wiki_revision_monitor_articles (
          article_id TEXT PRIMARY KEY,
          pack_id TEXT NOT NULL REFERENCES wiki_revision_monitor_packs(pack_id) ON DELETE CASCADE
        )
        """
    )
    ensure_read_model_schema(conn)
    conn.execute("INSERT INTO wiki_revision_monitor_packs(pack_id) VALUES('pack_one')")
    conn.execute("INSERT INTO wiki_revision_monitor_runs(run_id, pack_id) VALUES('run:pack_one:2026-03-31T00:00:00Z:abc', 'pack_one')")
    conn.execute("INSERT INTO wiki_revision_monitor_articles(article_id, pack_id) VALUES('article_1', 'pack_one')")

    replace_issue_packets(
        conn,
        run_id="run:pack_one:2026-03-31T00:00:00Z:abc",
        article_id="article_1",
        packet_rows=[
            {
                "pair_id": "pair:1",
                "packet_id": "packet:1",
                "packet_order": 0,
                "severity": "high",
                "summary": "event text changed",
                "event_id": "ev:1",
                "surfaces": ["narrative", "semantic"],
                "related_entities": ["Example"],
                "state_change_summary": ["actors"],
                "review_context": {"curated": {"curated_qids": ["Q1"]}},
            }
        ],
    )
    rows = issue_packet_rows(conn, run_id="run:pack_one:2026-03-31T00:00:00Z:abc", article_id="article_1")
    assert rows[0]["packet_id"] == "packet:1"
    assert rows[0]["severity"] == "high"
    assert rows[0]["review_context"]["curated"]["curated_qids"] == ["Q1"]


def test_revision_monitor_selected_pair_rows_round_trip() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("CREATE TABLE wiki_revision_monitor_packs (pack_id TEXT PRIMARY KEY)")
    conn.execute("CREATE TABLE wiki_revision_monitor_runs (run_id TEXT PRIMARY KEY, pack_id TEXT NOT NULL REFERENCES wiki_revision_monitor_packs(pack_id) ON DELETE CASCADE)")
    conn.execute(
        """
        CREATE TABLE wiki_revision_monitor_articles (
          article_id TEXT PRIMARY KEY,
          pack_id TEXT NOT NULL REFERENCES wiki_revision_monitor_packs(pack_id) ON DELETE CASCADE
        )
        """
    )
    ensure_read_model_schema(conn)
    conn.execute("INSERT INTO wiki_revision_monitor_packs(pack_id) VALUES('pack_one')")
    conn.execute("INSERT INTO wiki_revision_monitor_runs(run_id, pack_id) VALUES('run:pack_one:2026-03-31T00:00:00Z:abc', 'pack_one')")
    conn.execute("INSERT INTO wiki_revision_monitor_articles(article_id, pack_id) VALUES('article_1', 'pack_one')")

    replace_selected_pairs(
        conn,
        run_id="run:pack_one:2026-03-31T00:00:00Z:abc",
        article_id="article_1",
        pair_rows=[
            {
                "pair_id": "pair:1",
                "pair_kind": "largest_delta_in_window",
                "pair_kinds": ["largest_delta_in_window"],
                "older_revid": 1,
                "newer_revid": 2,
                "candidate_score": 9.5,
                "top_severity": "high",
                "pair_report_path": "/tmp/pair.json",
                "top_changed_sections": [{"section": "History", "touched_bytes": 1200}],
            }
        ],
    )
    rows = selected_pair_rows(conn, run_id="run:pack_one:2026-03-31T00:00:00Z:abc", article_id="article_1")
    assert rows[0]["pair_id"] == "pair:1"
    assert rows[0]["pair_kind"] == "largest_delta_in_window"
    assert rows[0]["top_changed_sections"][0]["section"] == "History"


def test_revision_monitor_contested_graph_payload_from_sqlite() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("CREATE TABLE wiki_revision_monitor_packs (pack_id TEXT PRIMARY KEY)")
    conn.execute("CREATE TABLE wiki_revision_monitor_runs (run_id TEXT PRIMARY KEY, pack_id TEXT NOT NULL REFERENCES wiki_revision_monitor_packs(pack_id) ON DELETE CASCADE)")
    conn.execute(
        """
        CREATE TABLE wiki_revision_monitor_articles (
          article_id TEXT PRIMARY KEY,
          pack_id TEXT NOT NULL REFERENCES wiki_revision_monitor_packs(pack_id) ON DELETE CASCADE,
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
    ensure_read_model_schema(conn)
    conn.execute("INSERT INTO wiki_revision_monitor_packs(pack_id) VALUES('pack_one')")
    conn.execute("INSERT INTO wiki_revision_monitor_runs(run_id, pack_id) VALUES('run:pack_one:2026-03-31T00:00:00Z:abc', 'pack_one')")
    conn.execute(
        """
        INSERT INTO wiki_revision_monitor_articles(
          article_id, pack_id, wiki, title, role, topics_json, review_context_json, article_order
        ) VALUES('article_1', 'pack_one', 'enwiki', 'Example Article', 'baseline', '[]', '{}', 0)
        """
    )
    conn.execute(
        """
        INSERT INTO wiki_revision_monitor_contested_graphs(
          run_id, article_id, graph_path, graph_json, region_count, cycle_count, selected_pair_count,
          changed_event_count, changed_attribution_count, highest_severity, hottest_region_json
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "run:pack_one:2026-03-31T00:00:00Z:abc",
            "article_1",
            "/tmp/graph.json",
            "{}",
            1,
            0,
            1,
            1,
            1,
            "high",
            '{"region_id":"region:1","title":"History"}',
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
            '{"region_id":"region:1","title":"History","touch_count":2,"total_touched_bytes":1200,"highest_severity":"high","graph_heat":1700.0}',
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
            '{"edge_id":"edge:1","edge_kind":"changes_event","source_id":"pair:1","target_id":"ev:1"}',
        ),
    )
    conn.execute(
        """
        INSERT INTO wiki_revision_monitor_contested_events(
          run_id, article_id, event_id, event_json
        ) VALUES(?,?,?,?)
        """,
        ("run:pack_one:2026-03-31T00:00:00Z:abc", "article_1", "ev:1", '{"event_id":"ev:1"}'),
    )
    conn.execute(
        """
        INSERT INTO wiki_revision_monitor_contested_epistemic(
          run_id, article_id, epistemic_id, epistemic_json
        ) VALUES(?,?,?,?)
        """,
        ("run:pack_one:2026-03-31T00:00:00Z:abc", "article_1", "epi:1", '{"epistemic_id":"epi:1","event_id":"ev:1"}'),
    )
    replace_selected_pairs(
        conn,
        run_id="run:pack_one:2026-03-31T00:00:00Z:abc",
        article_id="article_1",
        pair_rows=[
            {
                "pair_id": "pair:1",
                "pair_kind": "largest_delta_in_window",
                "pair_kinds": ["largest_delta_in_window"],
                "older_revid": 1,
                "newer_revid": 2,
                "candidate_score": 9.5,
                "top_severity": "high",
                "pair_report_path": "/tmp/pair.json",
                "top_changed_sections": [{"section": "History", "touched_bytes": 1200}],
            }
        ],
    )
    payload = contested_graph_payload(conn, run_id="run:pack_one:2026-03-31T00:00:00Z:abc", article_id="article_1")
    assert payload is not None
    assert payload["article"]["article_id"] == "article_1"
    assert payload["selected_pairs"][0]["pair_id"] == "pair:1"
    assert payload["regions"][0]["region_id"] == "region:1"
    assert payload["events"][0]["event_id"] == "ev:1"
    assert payload["epistemic_surfaces"][0]["epistemic_id"] == "epi:1"
