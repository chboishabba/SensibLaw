from __future__ import annotations

import json
from pathlib import Path

from scripts.au_fact_review import main
from src.wiki_timeline.sqlite_store import persist_wiki_timeline_aoo_run


def test_au_fact_review_script_bundle_emits_review_bundle(tmp_path: Path, capsys) -> None:
    db_path = tmp_path / "itir.sqlite"
    seed_path = Path(__file__).resolve().parents[1] / "data" / "ontology" / "au_semantic_linkage_seed_v1.json"
    persist_wiki_timeline_aoo_run(
        db_path=db_path,
        out_payload={
            "generated_at": "2026-03-07T00:00:00Z",
            "parser": {"name": "fixture"},
            "source_timeline": {"path": str(tmp_path / "wiki_timeline_hca_s942025_aoo.json"), "snapshot": None},
            "events": [
                {
                    "event_id": "ev1",
                    "anchor": {"year": 1936, "text": "1936"},
                    "section": "Criminal appeal",
                    "text": "In House v The King the appellant brought an appeal and the matter was heard by the High Court.",
                }
            ],
        },
        timeline_path=tmp_path / "wiki_timeline_hca_s942025_aoo.json",
    )

    exit_code = main(
        [
            "--db-path",
            str(db_path),
            "--seed-path",
            str(seed_path),
            "bundle",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["version"] == "fact.review.bundle.v1"
    assert payload["run"]["workflow_link"]["workflow_kind"] == "au_semantic"
    assert payload["summary"]["fact_count"] == 1
    assert payload["summary"]["event_count"] >= 1
    assert "operator_views" in payload
    assert any(row["event_type"] in {"appealed", "heard by"} for row in payload["events"])


def test_au_fact_review_script_run_emits_summary_ids(tmp_path: Path, capsys) -> None:
    db_path = tmp_path / "itir.sqlite"
    seed_path = Path(__file__).resolve().parents[1] / "data" / "ontology" / "au_semantic_linkage_seed_v1.json"
    persisted = persist_wiki_timeline_aoo_run(
        db_path=db_path,
        out_payload={
            "generated_at": "2026-03-07T00:00:00Z",
            "parser": {"name": "fixture"},
            "source_timeline": {"path": str(tmp_path / "wiki_timeline_hca_s942025_aoo.json"), "snapshot": None},
            "events": [
                {
                    "event_id": "ev1",
                    "anchor": {"year": 1992, "text": "1992"},
                    "section": "Native title",
                    "text": "In Mabo [No 2], the High Court rejected terra nullius and recognized native title against the Commonwealth of Australia.",
                }
            ],
        },
        timeline_path=tmp_path / "wiki_timeline_hca_s942025_aoo.json",
        run_id_override="au-fact-script-v1",
    )

    exit_code = main(
        [
            "--db-path",
            str(db_path),
            "--seed-path",
            str(seed_path),
            "--run-id",
            persisted.run_id,
            "run",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["semanticRunId"] == persisted.run_id
    assert payload["factRunId"].startswith("factrun:")
    assert payload["workflowLink"]["workflow_kind"] == "au_semantic"
    assert payload["reopenQuery"]["workflowKind"] == "au_semantic"
    assert payload["latestSourceQuery"]["workflowKind"] == "au_semantic"
    assert payload["factPersist"]["statement_count"] == 1
    assert payload["bundleSummary"]["fact_count"] == 1
