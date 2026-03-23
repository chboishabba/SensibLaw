from __future__ import annotations

import sqlite3
import json
import os
import tempfile
from pathlib import Path
from src.reporting.structure_report import TextUnit
from src.fact_intake import (
    build_fact_intake_payload_from_text_units,
    persist_fact_intake_payload,
    build_fact_review_workbench_payload,
)

def test_zelph_identifies_linkspam_as_volatility_signal() -> None:
    conn = sqlite3.connect(":memory:")
    units = [
        TextUnit(
            unit_id="unit:linkspam",
            source_id="wiki-spam",
            source_type="wiki_article",
            text="Revision by Linker22: inserted external blog claiming the verdict flipped, added tracking link, and removed citation tags.",
        ),
    ]
    payload = build_fact_intake_payload_from_text_units(units, source_label="zelph_spam_test")
    
    for source in payload["sources"]:
        source["source_type"] = "wiki_article"
        source.setdefault("provenance", {})["source_signal_classes"] = ["wiki_article"]

    persist_fact_intake_payload(conn, payload)
    
    workbench = build_fact_review_workbench_payload(conn, run_id=payload["run"]["run_id"])
    
    # We should add a rule for "blog" or "external" if it's not there, 
    # but "removed" is already in _REVERSION_KEYWORDS, so it might work 'for free'.
    spam_fact = next(row for row in workbench["facts"] if "linker22" in row["canonical_label"].lower())
    assert "volatility_signal" in spam_fact["signal_classes"]

def test_zelph_identifies_wiki_wikidata_alignment() -> None:
    conn = sqlite3.connect(":memory:")
    # Fact that appears in both wiki and wikidata
    units = [
        TextUnit(
            unit_id="unit:wiki_claim",
            source_id="wiki-article",
            source_type="wiki_article",
            text="The court ruled in favor of the plaintiff.",
        ),
        TextUnit(
            unit_id="unit:wikidata_claim",
            source_id="wikidata-sheet",
            source_type="wikidata_claim_sheet",
            text="The court ruled in favor of the plaintiff.",
        ),
    ]
    # In a real scenario, these would be merged into one fact.
    # Here we simulate a fact having both source types.
    payload = build_fact_intake_payload_from_text_units(units, source_label="zelph_alignment_test")
    
    # Manually simulate a merged fact with multiple sources
    for source in payload["sources"]:
        original_type = source.get("source_type")
        if original_type == "wiki_article":
            source["source_type"] = "wiki_article"
        else:
            source["source_type"] = "wikidata_claim_sheet"

    persist_fact_intake_payload(conn, payload)
    
    # To test alignment, we need a single fact that references both sources.
    # build_fact_intake_payload_from_text_units creates separate facts.
    # We'll modify the payload to merge them.
    fact1 = payload["fact_candidates"][0]
    fact2 = payload["fact_candidates"][1]
    
    merged_fact = {
        "fact_id": "fact:merged",
        "canonical_label": fact1["canonical_label"],
        "fact_text": fact1["fact_text"],
        "fact_type": "statement_capture",
        "candidate_status": "captured",
        "statement_ids": fact1["statement_ids"] + fact2["statement_ids"],
        "source_ids": [payload["sources"][0]["source_id"], payload["sources"][1]["source_id"]],
        "provenance": {"merged": True}
    }
    payload["fact_candidates"] = [merged_fact]
    
    # Reset the connection because we are changing the payload structure
    conn = sqlite3.connect(":memory:")
    persist_fact_intake_payload(conn, payload)
    
    workbench = build_fact_review_workbench_payload(conn, run_id=payload["run"]["run_id"])
    
    merged_fact_row = workbench["facts"][0]
    assert "wiki_wikidata_claim_alignment" in merged_fact_row["signal_classes"]

def test_zelph_persistence_survives_reconnection() -> None:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        conn = sqlite3.connect(db_path)
        units = [
            TextUnit(
                unit_id="unit:persist",
                source_id="wiki-persist",
                source_type="wiki_article",
                text="Revision by PersistenceBot: Reverted change due to lack of sources.",
            ),
        ]
        payload = build_fact_intake_payload_from_text_units(units, source_label="zelph_persistence_test")
        for source in payload["sources"]:
            source["source_type"] = "wiki_article"
        
        persist_fact_intake_payload(conn, payload)
        conn.close()
        
        # Re-open connection
        conn2 = sqlite3.connect(db_path)
        workbench = build_fact_review_workbench_payload(conn2, run_id=payload["run"]["run_id"])
        
        fact = workbench["facts"][0]
        assert "volatility_signal" in fact["signal_classes"]
        assert workbench["zelph"]["rule_status"] == "engine_ok"
        conn2.close()
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)

def test_zelph_db_atom_ingest_and_sentinel_inference() -> None:
    conn = sqlite3.connect(":memory:")
    # We create a fake document source
    units = [
        TextUnit(
            unit_id="unit:sentinel",
            source_id="doc_sentinel_1",
            source_type="wiki_article",
            text="Revision by Sentinel33: Reverted unexplained deletion of sourced content.",
        ),
    ]
    payload = build_fact_intake_payload_from_text_units(units, source_label="doc_sentinel_1")
    for source in payload["sources"]:
        source["source_type"] = "wiki_article"
        source.setdefault("provenance", {})["source_signal_classes"] = ["wiki_article"]
    for statement in payload["statements"]:
        statement["speaker_label"] = "Sentinel33"

    persist_fact_intake_payload(conn, payload)

    # Inject a mock rule_atom to match the extracted doc_id "doc_sentinel_1"
    # Ensure all tables are ready
    from src.fact_intake.read_model import _ensure_fact_intake_tables
    _ensure_fact_intake_tables(conn)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS rule_atoms (
            doc_id TEXT NOT NULL,
            stable_id TEXT NOT NULL,
            party TEXT,
            role TEXT,
            modality TEXT,
            action TEXT,
            scope TEXT,
            provision_id TEXT,
            rule_id TEXT,
            rev_id TEXT,
            toc_id TEXT,
            text_hash TEXT
        )
        """
    )
    conn.execute(
        """
        INSERT INTO rule_atoms (doc_id, stable_id, party, role, modality, action, scope, provision_id, rule_id, rev_id, toc_id, text_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("doc_sentinel_1", "stable_atom_ex", "community_member", "wiki_sentinel", "must", "revert_vandalism", "wiki_scope", "prov_1", "rule_1", "rev_1", "toc_1", "hash_1")
    )
    conn.commit()

    workbench = build_fact_review_workbench_payload(conn, run_id=payload["run"]["run_id"])

    # 1. Verify the rule_atom got packed into the payload
    assert len(workbench.get("rule_atoms", [])) == 1
    assert workbench["rule_atoms"][0]["doc_id"] == "doc_sentinel_1"
    assert workbench["rule_atoms"][0]["role"] == "wiki_sentinel"
    assert workbench["rule_atoms"][0]["modality"] == "must"

    # 2. Verify Zelph bridge generated engine output for the atom 
    triples = workbench["zelph"]["triples"]
    print(f"DEBUG: SENTINEL TRIPLES: {json.dumps(triples, indent=2)}")

    # Check that the logic inferring Sentinel33 as a wiki sentinel successfully ran
    sentinel_inferred = False
    for t in triples:
        if t["subject"] == "Sentinel33" and t["predicate"] == "is" and t["object"] == "wiki sentinel":
            sentinel_inferred = True
            break

    assert sentinel_inferred, f"Zelph failed to use recursive lists to deduce Sentinel33 is a wiki sentinel. Triples: {json.dumps(triples, indent=2)}"

def test_zelph_identifies_authority_transfer_risk() -> None:
    conn = sqlite3.connect(":memory:")
    # Fact from wiki WITHOUT a corresponding legal source
    units = [
        TextUnit(
            unit_id="unit:wiki_only",
            source_id="wiki-unverified",
            source_type="wiki_article",
            text="The defendant was eventually acquitted.",
        ),
    ]
    payload = build_fact_intake_payload_from_text_units(units, source_label="zelph_risk_test")
    # Force the source to be ONLY wiki_article
    for source in payload["sources"]:
        source["source_type"] = "wiki_article"
        source.setdefault("provenance", {})["source_signal_classes"] = ["wiki_article"]
        
    persist_fact_intake_payload(conn, payload)
    workbench = build_fact_review_workbench_payload(conn, run_id=payload["run"]["run_id"])
    
    fact = workbench["facts"][0]
    # In zelph_workbench_rules.zlp:
    # (X "source_signal_class" "public_summary", not(X "source_signal_class" "legal_record")...) => risk
    assert "public_summary" in fact["source_signal_classes"]
    assert "authority_transfer_risk" in fact["signal_classes"]
    assert "public_knowledge_not_authority" not in fact["signal_classes"]

def test_zelph_avoids_false_volatility_signal_on_legal_transcript() -> None:
    conn = sqlite3.connect(":memory:")
    # Transcript where someone says "reverted" in a legal sense, not a Wiki sense
    units = [
        TextUnit(
            unit_id="unit:legal_revert",
            source_id="legal-doc-1",
            source_type="legal_record",
            text="The ownership of the property reverted to the original grantor.",
        ),
    ]
    payload = build_fact_intake_payload_from_text_units(units, source_label="zelph_negative_test")
    # Force the source to be legal_record
    for source in payload["sources"]:
        source["source_type"] = "legal_record"
        source.setdefault("provenance", {})["source_signal_classes"] = ["legal_record"]
        
    persist_fact_intake_payload(conn, payload)
    workbench = build_fact_review_workbench_payload(conn, run_id=payload["run"]["run_id"])
    
    fact = workbench["facts"][0]
    # Should NOT have volatility_signal because it's not a wiki revision
    # Lexical packs like 'au_legal' should not trigger 'volatility_signal' either
    assert "volatility_signal" not in fact["signal_classes"]
    assert "reversion_edit" not in fact["signal_classes"]
