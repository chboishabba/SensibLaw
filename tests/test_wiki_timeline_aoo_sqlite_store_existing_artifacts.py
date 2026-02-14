import json
import sqlite3
from pathlib import Path

import pytest

from src.wiki_timeline.sqlite_store import persist_wiki_timeline_aoo_run


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _count_events(payload: dict) -> int:
    events = payload.get("events") or []
    if not isinstance(events, list):
        return 0
    n = 0
    for ev in events:
        if not isinstance(ev, dict):
            continue
        if str(ev.get("event_id") or "").strip():
            n += 1
    return n


def _iter_sample_events(payload: dict, limit: int = 5) -> list[dict]:
    events = payload.get("events") or []
    out: list[dict] = []
    if not isinstance(events, list):
        return out
    for ev in events:
        if not isinstance(ev, dict):
            continue
        if not str(ev.get("event_id") or "").strip():
            continue
        out.append(ev)
        if len(out) >= limit:
            break
    return out


@pytest.mark.parametrize(
    "artifact_rel",
    [
        "SensibLaw/.cache_local/wiki_timeline_gwb_aoo.json",
        "SensibLaw/.cache_local/wiki_timeline_hca_s942025_aoo.json",
    ],
)
def test_persist_sqlite_against_existing_json_artifact(tmp_path: Path, artifact_rel: str) -> None:
    artifact_path = Path(artifact_rel)
    if not artifact_path.exists():
        pytest.skip(f"missing local artifact: {artifact_rel}")

    payload = _load_json(artifact_path)

    # Prefer declared source inputs if present; fall back to the artifact path itself.
    timeline_path = None
    try:
        declared = payload.get("source_timeline", {}).get("path")
        if declared:
            p = Path(str(declared))
            if p.exists():
                timeline_path = p
    except Exception:
        timeline_path = None
    timeline_path = timeline_path or artifact_path

    profile_path = None
    try:
        declared = payload.get("extraction_profile", {}).get("path")
        if declared:
            p = Path(str(declared))
            if p.exists():
                profile_path = p
    except Exception:
        profile_path = None

    extractor_path = Path("SensibLaw/scripts/wiki_timeline_aoo_extract.py")
    if not extractor_path.exists():
        extractor_path = None  # type: ignore[assignment]

    db_path = tmp_path / "wiki_timeline_aoo.sqlite"

    expected_n = _count_events(payload)

    res1 = persist_wiki_timeline_aoo_run(
        db_path=db_path,
        out_payload=payload,
        timeline_path=timeline_path,
        profile_path=profile_path,
        extractor_path=extractor_path,
    )
    res2 = persist_wiki_timeline_aoo_run(
        db_path=db_path,
        out_payload=payload,
        timeline_path=timeline_path,
        profile_path=profile_path,
        extractor_path=extractor_path,
    )

    assert res1.run_id == res2.run_id
    assert res1.n_events == expected_n

    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        n_runs = conn.execute("SELECT COUNT(*) AS n FROM wiki_timeline_aoo_runs").fetchone()["n"]
        assert n_runs == 1
        n_events = conn.execute(
            "SELECT COUNT(*) AS n FROM wiki_timeline_aoo_events WHERE run_id = ?",
            (res1.run_id,),
        ).fetchone()["n"]
        assert n_events == expected_n

        # Roundtrip a few events and verify the stored JSON parses back to the same dict.
        for ev in _iter_sample_events(payload, limit=5):
            event_id = str(ev.get("event_id") or "").strip()
            row = conn.execute(
                """
                SELECT anchor_year, anchor_month, anchor_day, anchor_precision, anchor_kind, section, text, event_json
                FROM wiki_timeline_aoo_events
                WHERE run_id = ? AND event_id = ?
                """,
                (res1.run_id, event_id),
            ).fetchone()
            assert row is not None
            stored = json.loads(row["event_json"])
            assert stored == ev

            anchor = ev.get("anchor") or {}
            if isinstance(anchor, dict):
                # anchor fields are optional; just ensure equality when they exist and are numeric-ish.
                if anchor.get("year") is not None:
                    assert row["anchor_year"] == int(anchor.get("year"))
                if anchor.get("month") is not None:
                    assert row["anchor_month"] == int(anchor.get("month"))
                if anchor.get("day") is not None:
                    assert row["anchor_day"] == int(anchor.get("day"))
                if anchor.get("precision") is not None:
                    assert row["anchor_precision"] == str(anchor.get("precision"))
                if anchor.get("kind") is not None:
                    assert row["anchor_kind"] == str(anchor.get("kind"))

            if ev.get("section") is not None:
                assert row["section"] == str(ev.get("section"))
            if ev.get("text") is not None:
                assert row["text"] == str(ev.get("text"))

