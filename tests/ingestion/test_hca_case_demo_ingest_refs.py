from __future__ import annotations

import json
from pathlib import Path

from scripts import hca_case_demo_ingest as ingest


def _write_doc(path: Path) -> Path:
    payload = {
        "provisions": [
            {
                "stable_id": "prov-001",
                "text": "The Court applied s 6O of the Civil Liability Act and considered SC[210].",
                "references": [
                    ["civil liability act 2002", "section", "6O", "s 6O of the Civil Liability Act", None]
                ],
                "rule_tokens": {"references": ["Part 1B"]},
                "rule_atoms": [
                    {
                        "stable_id": "atom-001",
                        "text": "The Court considered SC[210].",
                        "references": [["supreme court reasons", "paragraph", "210", "SC[210]", None]],
                        "subject": {"refs": ["SC[210]"]},
                        "elements": [{"text": "SC[210] was cited", "references": ["SC[210]"]}],
                    }
                ],
            }
        ],
        "sentences": [
            {"index": 0, "text": "The Court applied s 6O of the Civil Liability Act and considered SC[210]."}
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_sl_reference_lane_extracts_and_links_follow_hints(tmp_path: Path) -> None:
    doc_path = _write_doc(tmp_path / "sample.document.json")

    rows = ingest._collect_sl_reference_rows(str(doc_path))
    assert rows, "expected SL rows from provisions/rule atoms"

    selected = ingest._select_sl_references_for_sentence(
        rows,
        "The Court applied s 6O of the Civil Liability Act and considered SC[210].",
        source_document_json=str(doc_path),
        source_pdf="sample.pdf",
    )
    assert selected, "expected sentence-linked SL references"

    first = selected[0]
    assert first.get("source_document_json") == str(doc_path)
    assert first.get("provision_stable_id") == "prov-001"
    assert "wiki_connector" in list(first.get("follower_order") or [])
    follow = list(first.get("follow") or [])
    assert any((h or {}).get("provider") == "wikipedia" for h in follow)
    assert any((h or {}).get("provider") == "wiki_connector" for h in follow)


def test_sb_payload_preserves_sl_references_lane() -> None:
    payload = {
        "events": [
            {
                "event_id": "ev:0001",
                "signal_class": "narrative_sentence",
                "anchor": {"year": 2025, "month": 7, "day": None},
                "section": "Narrative",
                "text": "Sample sentence.",
                "steps": [{"action": "held", "subjects": ["Court"], "objects": ["Act"], "purpose": "test"}],
                "citations": [{"text": "SC[210]"}],
                "sl_references": [{"lane": "provisions.references", "text": "s 6O of the Civil Liability Act"}],
                "warnings": [],
            }
        ]
    }
    out = ingest._build_sb_signal_payload("https://example.test", payload)
    signals = out.get("signals") or []
    assert isinstance(signals, list) and signals
    first = signals[0]
    assert first.get("citations")
    assert first.get("sl_references")
