import json
import sqlite3
from pathlib import Path

import pytest

from src.wiki_timeline.sqlite_store import load_run_payload_from_normalized, persist_wiki_timeline_aoo_run


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _count_events(payload: dict) -> int:
    events = payload.get("events") or []
    if not isinstance(events, list):
        return 0
    return sum(1 for ev in events if isinstance(ev, dict) and str(ev.get("event_id") or "").strip())


def _core_event_view(ev: dict) -> dict:
    return {
        "event_id": ev.get("event_id"),
        "anchor": ev.get("anchor"),
        "section": ev.get("section"),
        "text": ev.get("text"),
        "action": ev.get("action"),
    }


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
    timeline_path = Path(str(payload.get("source_timeline", {}).get("path") or artifact_path))
    if not timeline_path.exists():
        timeline_path = artifact_path

    profile_path = None
    declared_profile = payload.get("extraction_profile", {}).get("path")
    if isinstance(declared_profile, str) and Path(declared_profile).exists():
        profile_path = Path(declared_profile)

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
        # New storage should not keep full event blobs for new persists.
        legacy_blob_bytes = conn.execute(
            "SELECT SUM(LENGTH(event_json)) AS n FROM wiki_timeline_aoo_events WHERE run_id = ?",
            (res1.run_id,),
        ).fetchone()["n"]
        assert int(legacy_blob_bytes or 0) <= expected_n * 4

        roundtrip = load_run_payload_from_normalized(conn, res1.run_id)
        assert roundtrip is not None
        assert _count_events(roundtrip) == expected_n
        assert [_core_event_view(ev) for ev in roundtrip["events"][:3]] == [_core_event_view(ev) for ev in payload["events"][:3]]
