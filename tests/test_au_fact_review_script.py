from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3

from scripts.au_fact_review import main
from src.au_semantic.linkage import ensure_au_semantic_schema
from src.fact_intake import persist_authority_ingest_receipt
from src.gwb_us_law.semantic import ensure_gwb_semantic_schema
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
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        ensure_gwb_semantic_schema(conn)
        ensure_au_semantic_schema(conn)
        persist_authority_ingest_receipt(
            conn,
            {
                "version": "authority.ingest.v1",
                "authority_kind": "austlii",
                "ingest_mode": "known_authority_fetch",
                "citation": "[1936] HCA 40",
                "selection_reason": "by_citation:[1936] HCA 40",
                "resolved_url": "https://www.austlii.edu.au/cgi-bin/viewdoc/au/cases/cth/HCA/1936/40.html",
                "content_type": "text/html",
                "content_length": 120,
                "content_sha256": hashlib.sha256(b"house-v-the-king").hexdigest(),
                "body_preview_text": "House v The King judgment excerpt discussing the High Court appeal.",
                "segments": [
                    {
                        "segment_kind": "paragraph",
                        "paragraph_number": 1,
                        "segment_text": "House v The King concerned an appeal heard by the High Court.",
                    }
                ],
            },
        )

    exit_code = main(
        [
            "--db-path",
            str(db_path),
            "--seed-path",
            str(seed_path),
            "--include-authority-receipts",
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
    assert payload["semantic_context"]["authority_receipts"]["summary"]["authority_receipt_count"] >= 1
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
