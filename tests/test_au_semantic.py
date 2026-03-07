from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from src.au_semantic.linkage import ensure_au_semantic_schema, import_au_semantic_seed_payload
from src.au_semantic.semantic import (
    _load_au_legal_representation_cues,
    build_au_semantic_report,
    run_au_semantic_pipeline,
)
from src.gwb_us_law.semantic import ensure_gwb_semantic_schema
from src.wiki_timeline.sqlite_store import persist_wiki_timeline_aoo_run


def test_au_legal_representation_catalog_expands_parameterized_party_roles() -> None:
    cues = {row["surface"]: row["role_label"] for row in _load_au_legal_representation_cues()}
    assert cues["appeared for the respondent"] == "Counsel for Respondent"
    assert cues["senior counsel for the applicant"] == "Senior Counsel for Applicant"
    assert cues["junior counsel for the defendant"] == "Junior Counsel for Defendant"


def test_au_semantic_pipeline_creates_doc_local_participants_and_abstains_weak_forum(tmp_path: Path) -> None:
    db_path = tmp_path / "itir.sqlite"
    seed_path = Path(__file__).resolve().parents[1] / "data" / "ontology" / "au_semantic_linkage_seed_v1.json"
    seed_payload = json.loads(seed_path.read_text(encoding="utf-8"))
    timeline_payload = {
        "generated_at": "2026-03-07T00:00:00Z",
        "parser": {"name": "fixture"},
        "source_timeline": {"path": str(tmp_path / "wiki_timeline_hca_s942025_aoo.json"), "snapshot": None},
        "events": [
            {
                "event_id": "ev1",
                "anchor": {"year": 1936, "text": "1936"},
                "section": "Appeal",
                "text": "The appellant appealed and the matter was heard by the High Court in House v The King."
            },
            {
                "event_id": "ev2",
                "anchor": {"year": 2003, "text": "2003"},
                "section": "Judicial review",
                "text": "The plaintiff challenged the Native Title (NSW) Act 1994, but the Court was not separately identified."
            },
            {
                "event_id": "ev3",
                "anchor": {"year": 2003, "text": "2003"},
                "section": "Representation",
                "text": "The Attorney-General appeared with Mr Walker SC as senior counsel for the appellant and the Court held that House v The King applied."
            },
            {
                "event_id": "ev4",
                "anchor": {"year": 2004, "text": "2004"},
                "section": "Representation",
                "text": "Ms Tran K.C. appeared for the respondent and junior counsel for the appellant appeared later."
            },
            {
                "event_id": "ev5",
                "anchor": {"year": 2005, "text": "2005"},
                "section": "Representation",
                "text": "The government appeared for the respondent."
            },
        ],
    }
    persist_wiki_timeline_aoo_run(db_path=db_path, out_payload=timeline_payload, timeline_path=tmp_path / "wiki_timeline_hca_s942025_aoo.json")
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        ensure_gwb_semantic_schema(conn)
        ensure_au_semantic_schema(conn)
        import_au_semantic_seed_payload(conn, seed_payload)
        result = run_au_semantic_pipeline(conn)
        report = build_au_semantic_report(conn, run_id=result["run_id"])

    assert result["relation_candidate_count"] >= 2
    assert result["promoted_relation_count"] >= 1
    unresolved_surfaces = {row["surface_text"] for row in report["unresolved_mentions"]}
    assert "the Court" in unresolved_surfaces
    entity_keys = {row["entity"]["canonical_key"] for row in report["per_entity"]}
    assert any(key.startswith("actor:doc:") and key.endswith("appellant") for key in entity_keys)
    assert "office:attorney_general" in entity_keys
    assert any(key.startswith("actor:doc:") and key.endswith("mr_walker_sc") for key in entity_keys)
    assert any(key.startswith("actor:doc:") and key.endswith("ms_tran_k_c") for key in entity_keys)
    assert not any(key.endswith("counsel_for_respondent") for key in entity_keys)
    relation_predicates = {row["predicate_key"] for row in report["promoted_relations"]}
    assert "appealed" in relation_predicates or "heard_by" in relation_predicates
    candidate_predicates = {row["predicate_key"] for row in report["candidate_only_relations"]}
    assert "decided_by" in candidate_predicates or "applied" in relation_predicates
    abstained_reasons = {(row["surface_text"], row["resolution_rule"]) for row in report["unresolved_mentions"]}
    assert ("junior counsel for the appellant", "legal_representation_requires_named_representative_v1") in abstained_reasons
    assert ("appeared for the respondent", "legal_representation_requires_named_representative_v1") in abstained_reasons
