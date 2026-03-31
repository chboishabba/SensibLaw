from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from src.wiki_timeline.query_runtime import resolve_query_db_path
from src.wiki_timeline.sqlite_store import persist_wiki_timeline_aoo_run
from src.wiki_timeline.source_registry import resolve_source_config
from src.wiki_timeline.timeline_view_projection import build_timeline_view_projection


def test_build_timeline_view_projection_filters_and_sorts_events() -> None:
    payload = {
        "snapshot": {"title": "Example", "wiki": "demo", "revid": "42", "source_url": "https://example.test"},
        "events": [
            {
                "event_id": "ev:later",
                "text": "Later event",
                "section": "Narrative",
                "anchor": {"year": 2005, "month": 4, "day": 2, "precision": "day", "text": "2005-04-02", "kind": "mention"},
                "links": ["https://b.example"],
            },
            {
                "event_id": "ev:missing-text",
                "text": "",
                "section": "Narrative",
                "anchor": {"year": 1999},
                "links": [],
            },
            {
                "event_id": "ev:early",
                "text": "Early event",
                "section": "",
                "anchor": {"year": "2001", "month": "9", "day": "11", "precision": "day", "text": "2001-09-11", "kind": "mention"},
                "links": ["", "https://a.example"],
            },
        ],
    }

    out = build_timeline_view_projection(payload)
    assert out["snapshot"]["revid"] == 42
    assert [row["event_id"] for row in out["events"]] == ["ev:early", "ev:later"]
    assert out["events"][0]["section"] == "(unknown)"
    assert out["events"][0]["anchor"]["year"] == 2001
    assert out["events"][0]["links"] == ["https://a.example"]


def test_query_wiki_timeline_aoo_db_timeline_view_projection(tmp_path: Path) -> None:
    timeline_path = tmp_path / "wiki_timeline_gwb.json"
    timeline_path.write_text(json.dumps({"snapshot": {"title": "x"}, "events": []}, sort_keys=True), encoding="utf-8")
    db_path = tmp_path / "itir.sqlite"

    payload = {
        "generated_at": "2026-03-30T00:00:00Z",
        "source_timeline": {"path": str(timeline_path), "snapshot": {"title": "x"}},
        "root_actor": {"label": "Root", "surname": "Actor"},
        "snapshot": {"title": "Example", "wiki": "demo", "revid": "42", "source_url": "https://example.test"},
        "events": [
            {
                "event_id": "ev:later",
                "anchor": {"year": 2005, "month": 4, "day": 2, "precision": "day", "kind": "mention", "text": "2005-04-02"},
                "section": "Narrative",
                "text": "Later event",
                "links": ["https://b.example"],
            },
            {
                "event_id": "ev:early",
                "anchor": {"year": 2001, "month": 9, "day": 11, "precision": "day", "kind": "mention", "text": "2001-09-11"},
                "section": "",
                "text": "Early event",
                "links": ["https://a.example"],
            },
        ],
    }

    persist_wiki_timeline_aoo_run(
        db_path=db_path,
        out_payload=payload,
        timeline_path=timeline_path,
        extractor_path=Path("SensibLaw/scripts/wiki_timeline_aoo_extract.py"),
    )

    script = Path("SensibLaw/scripts/query_wiki_timeline_aoo_db.py")
    proc = subprocess.run(
        [
            sys.executable,
            str(script),
            "--db-path",
            str(db_path),
            "--timeline-path-suffix",
            timeline_path.name,
            "--projection",
            "timeline_view",
        ],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0
    parsed = json.loads(proc.stdout)
    assert parsed["snapshot"]["revid"] == 42
    assert [row["event_id"] for row in parsed["events"]] == ["ev:early", "ev:later"]
    assert parsed["events"][0]["section"] == "(unknown)"


def test_query_wiki_timeline_aoo_db_source_key_meta_envelope(tmp_path: Path) -> None:
    timeline_path = tmp_path / "wiki_timeline_gwb.json"
    timeline_path.write_text(json.dumps({"snapshot": {"title": "x"}, "events": []}, sort_keys=True), encoding="utf-8")
    db_path = tmp_path / "itir.sqlite"

    payload = {
        "generated_at": "2026-03-30T00:00:00Z",
        "source_timeline": {"path": str(timeline_path), "snapshot": {"title": "x"}},
        "root_actor": {"label": "Root", "surname": "Actor"},
        "snapshot": {"title": "Example", "wiki": "demo", "revid": "42", "source_url": "https://example.test"},
        "events": [
            {
                "event_id": "ev:one",
                "anchor": {"year": 2001, "precision": "year", "kind": "mention", "text": "2001"},
                "section": "Narrative",
                "text": "First event",
                "links": [],
            }
        ],
    }

    persist_wiki_timeline_aoo_run(
        db_path=db_path,
        out_payload=payload,
        timeline_path=timeline_path,
        extractor_path=Path("SensibLaw/scripts/wiki_timeline_aoo_extract.py"),
    )

    script = Path("SensibLaw/scripts/query_wiki_timeline_aoo_db.py")
    proc = subprocess.run(
        [
            sys.executable,
            str(script),
            "--db-path",
            str(db_path),
            "--source-key",
            "gwb",
            "--projection",
            "timeline_view",
            "--with-source-meta",
        ],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0
    parsed = json.loads(proc.stdout)
    assert parsed["source"] == "gwb"
    assert parsed["timeline_suffix"] == "wiki_timeline_gwb.json"
    assert parsed["rel_path"] == "SensibLaw/.cache_local/wiki_timeline_gwb.json"
    assert parsed["payload"]["events"][0]["event_id"] == "ev:one"


def test_source_registry_supports_aoo_all_variant_for_gwb_corpus() -> None:
    config = resolve_source_config("gwb_corpus_v1", projection="raw", fallback="hca", variant="aoo_all")
    assert config["source"] == "gwb_corpus_v1"
    assert config["timeline_suffix"] == "wiki_timeline_gwb_corpus_v1.json"
    assert config["rel_path"].endswith("wiki_timeline_gwb_corpus_v1.json")


def test_query_runtime_prefers_explicit_db_path(monkeypatch: Any, tmp_path: Path) -> None:
    explicit = tmp_path / "explicit.sqlite"
    monkeypatch.setenv("ITIR_DB_PATH", str(tmp_path / "env.sqlite"))
    assert resolve_query_db_path(str(explicit)) == explicit.resolve()


def test_query_runtime_falls_back_to_modern_then_legacy_env(monkeypatch: Any, tmp_path: Path) -> None:
    modern = tmp_path / "modern.sqlite"
    legacy = tmp_path / "legacy.sqlite"
    monkeypatch.setenv("ITIR_DB_PATH", str(modern))
    monkeypatch.setenv("SL_WIKI_TIMELINE_DB", str(legacy))
    assert resolve_query_db_path() == modern.resolve()
    monkeypatch.delenv("ITIR_DB_PATH")
    assert resolve_query_db_path() == legacy.resolve()
