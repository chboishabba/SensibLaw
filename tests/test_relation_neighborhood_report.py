from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from src.ontology.entity_bridge import ensure_bridge_schema, ensure_seeded_bridge_slice, import_bridge_payload, lookup_bridge_alias
from src.reporting.relation_neighborhood_report import build_relation_neighborhood_report
from src.reporting.structure_report import TextUnit


def test_lookup_bridge_alias_resolves_seeded_un_alias() -> None:
    with sqlite3.connect(":memory:") as conn:
        conn.row_factory = sqlite3.Row
        ensure_bridge_schema(conn)
        ensure_seeded_bridge_slice(conn)
        links = lookup_bridge_alias("UN", conn=conn)
    assert any(link.curie == "wikidata:Q1065" for link in links)


def test_relation_neighborhood_report_emits_top_terms_and_bridge_hits() -> None:
    units = [
        TextUnit(
            unit_id="u1",
            source_id="s1",
            source_type="text_file",
            text="Camus discussed philosophy and art. Picasso discussed art. The UN discussed philosophy.",
        ),
        TextUnit(
            unit_id="u2",
            source_id="s1",
            source_type="text_file",
            text="Freire and hooks discussed feminism and philosophy.",
        ),
    ]
    with sqlite3.connect(":memory:") as conn:
        conn.row_factory = sqlite3.Row
        ensure_bridge_schema(conn)
        ensure_seeded_bridge_slice(conn)
        report = build_relation_neighborhood_report(units, top_k=10, top_n_neighbors=4, conn=conn)
    terms = {row["term"]: row for row in report["top_terms"]}
    assert "art" in terms
    assert "philosophy" in terms
    assert any(row["term"] in {"camus", "picasso", "freire", "hooks"} for row in report["top_terms"])
    assert any(item["term"] == "philosophy" for item in report["top_topic_interconnects"])
    assert any(link["curie"] == "wikidata:Q1065" for link in terms.get("un", {}).get("bridge_matches", []))


def test_relation_neighborhood_report_emits_au_branch_bridge_hits() -> None:
    bridge_path = Path(__file__).resolve().parents[1] / "data" / "ontology" / "external_ref_bridge_prepopulation_core_v1.json"
    payload = json.loads(bridge_path.read_text(encoding="utf-8"))
    units = [
        TextUnit(
            unit_id="u1",
            source_id="s1",
            source_type="text_file",
            text=(
                "In Mabo v Queensland (No 2), Eddie Mabo and the High Court of Australia "
                "reframed native title in the Commonwealth of Australia under the Native Title Act 1993."
            ),
        )
    ]
    with sqlite3.connect(":memory:") as conn:
        conn.row_factory = sqlite3.Row
        ensure_bridge_schema(conn)
        import_bridge_payload(conn, payload)
        report = build_relation_neighborhood_report(
            units,
            top_k=12,
            top_n_neighbors=5,
            conn=conn,
            slice_name="prepopulation_core_refs_v1",
        )
    terms = {row["term"]: row for row in report["top_terms"]}
    assert any(link["canonical_ref"] == "case:mabo_v_queensland_no_2" for link in terms.get("mabo", {}).get("bridge_matches", []))
    assert any(link["canonical_ref"] == "jurisdiction:commonwealth_of_australia" for link in terms.get("australia", {}).get("bridge_matches", []))
