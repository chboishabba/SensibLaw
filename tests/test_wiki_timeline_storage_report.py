from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.wiki_timeline.sqlite_store import persist_wiki_timeline_aoo_run


def test_storage_report_new_persist_has_zero_residual_blob_bytes(tmp_path: Path) -> None:
    timeline_path = tmp_path / "wiki_timeline_gwb.json"
    timeline_path.write_text(json.dumps({"snapshot": {"title": "x"}, "events": []}, sort_keys=True), encoding="utf-8")
    db_path = tmp_path / "itir.sqlite"

    payload = {
        "generated_at": "2026-03-07T00:00:00Z",
        "source_timeline": {"path": str(timeline_path), "snapshot": {"title": "x"}},
        "events": [
            {
                "event_id": "ev:1",
                "anchor": {"year": 2001, "month": 9, "day": 11, "precision": "day", "kind": "mention", "text": "September 11, 2001"},
                "section": "Narrative",
                "text": "Civil Liability Act 2002 (NSW) s 5B(2)(a) was discussed.",
                "actors": [{"label": "A", "resolved": "A", "role": "subject", "source": "fixture"}],
                "objects": [{"title": "B", "source": "wikilink", "resolver_hints": [{"kind": "exact", "title": "B"}]}],
                "steps": [
                    {
                        "action": "discuss",
                        "action_meta": {"tense": "past"},
                        "subjects": ["A"],
                        "objects": ["B"],
                    }
                ],
                "links": ["B"],
                "citations": [{"text": "cite"}],
                "span_candidates": [{"text": "candidate", "start": 0, "end": 9}],
            }
        ],
        "fact_timeline": [{"fact_id": "f1", "text": "Example fact"}],
    }

    res = persist_wiki_timeline_aoo_run(
        db_path=db_path,
        out_payload=payload,
        timeline_path=timeline_path,
        extractor_path=Path("SensibLaw/scripts/wiki_timeline_aoo_extract.py"),
    )

    script = Path("SensibLaw/scripts/wiki_timeline_storage_report.py")
    proc = subprocess.run(
        [
            sys.executable,
            str(script),
            "--db-path",
            str(db_path),
            "--run-id",
            res.run_id,
        ],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        check=True,
    )

    report = json.loads(proc.stdout)
    assert report["run_id"] == res.run_id
    assert int(report["residual_blob_bytes"]) == 0
    assert int(report["normalized_bytes_estimate"]) > 0
