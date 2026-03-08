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


def test_hca_case_snapshot_and_source_entity_are_non_null() -> None:
    manifest = {"generated_at": "2026-03-09T01:02:03+00:00"}
    snapshot = ingest._build_hca_case_snapshot("https://www.hcourt.gov.au/cases-and-judgments/cases/decided/case-s942025", manifest)
    assert snapshot["title"] == "AA v Diocese (S94/2025)"
    assert snapshot["wiki"] == "hca_case_s942025"
    assert snapshot["source_url"] == "https://www.hcourt.gov.au/cases-and-judgments/cases/decided/case-s942025"
    assert snapshot["rev_timestamp"] == "2026-03-09T01:02:03+00:00"

    source_entity = ingest._build_hca_source_entity(str(snapshot["source_url"]), snapshot)
    assert source_entity["type"] == "court_opinion"
    assert source_entity["title"] == "AA v Diocese (S94/2025)"
    assert source_entity["url"] == snapshot["source_url"]
    assert source_entity["publication_date"] == snapshot["rev_timestamp"]


def test_hca_narrative_sentence_filter_rejects_reference_heavy_lines() -> None:
    assert (
        ingest._is_narrative_sentence(
            "T85.40–42 (evidence of AA) (ABFM vol 2 at 602); T115.32ff and T120.40–42 (Mr Perry) (ABFM vol 2 at 632, 637)."
        )
        is False
    )


def test_reasoning_proposition_layer_extracts_negated_against_idiom() -> None:
    facts = [
        {
            "fact_id": "ev:0349:f01",
            "event_id": "ev:0349",
            "action": "attend",
            "subjects": ["the appellant", "Mr Perry"],
            "objects": ["the Presbytery", "Fr Picken"],
            "text": "The appellant and Mr Perry attended the Presbytery with Fr Picken.",
        },
        {
            "fact_id": "ev:0349:f02",
            "event_id": "ev:0349",
            "action": "supply",
            "subjects": ["Fr Picken"],
            "objects": ["cigarettes", "alcohol"],
            "text": "Fr Picken supplied them with cigarettes and alcohol.",
        },
    ]

    propositions, links = ingest._build_propositions_for_event(
        event_id="ev:0349",
        sentence_text=(
            "Given it was undisputed that the appellant and Mr Perry did attend the Presbytery with Fr Picken, "
            "who did supply them with cigarettes and alcohol — and that Fr Picken did begin to teach them "
            "religious education in 1969 — any imprecision in the precise timing of those visits cannot be seen "
            "as telling against acceptance that the abuse occurred as the appellant alleged."
        ),
        timeline_facts=facts,
    )

    assert any(p.get("predicate_key") == "attend" for p in propositions)
    reasoning = next(p for p in propositions if p.get("proposition_kind") == "reasoning")
    assert reasoning["predicate_key"] == "negate"
    assert reasoning["negation"]["kind"] == "not"
    assert reasoning["source_signal"] == "idiom_against"
    assert {"role": "subject", "value": "any imprecision in the precise timing of those visits"} in reasoning["arguments"]
    assert any(arg.get("role") == "object" and "acceptance that the abuse occurred" in str(arg.get("value")) for arg in reasoning["arguments"])
    assert all(link["link_kind"] == "supports" for link in links)
    assert {link["source_proposition_id"] for link in links} == {"ev:0349:f01:p", "ev:0349:f02:p"}
