from __future__ import annotations

import sqlite3

from src.ontology.entity_bridge import ensure_bridge_schema, ensure_seeded_bridge_slice, lookup_bridge_alias
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
