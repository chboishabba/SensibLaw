from __future__ import annotations

import sqlite3
import json
from src.reporting.structure_report import TextUnit
from src.fact_intake import (
    build_fact_intake_payload_from_text_units,
    persist_fact_intake_payload,
    build_fact_review_workbench_payload,
)

def test_zelph_identifies_vandalism_and_dispute_as_volatility_signals() -> None:
    conn = sqlite3.connect(":memory:")
    units = [
        TextUnit(
            unit_id="unit:vandal",
            source_id="wiki-vandal",
            source_type="wiki_article",
            text="Revision by Editor1: Reverted vandalism by 1.2.3.4.",
        ),
        TextUnit(
            unit_id="unit:dispute",
            source_id="wiki-dispute",
            source_type="wiki_article",
            text="Revision by Editor2: Disputed change; pending verification of sources.",
        ),
        TextUnit(
            unit_id="unit:admin",
            source_id="wiki-admin",
            source_type="wiki_article",
            text="Revision by Admin: Warning issued to user regarding unsourced claims.",
        ),
    ]
    payload = build_fact_intake_payload_from_text_units(units, source_label="zelph_volatility_test")
    
    # We need to set the source_type correctly so the lexical projection triggers
    for source in payload["sources"]:
        source["source_type"] = "wiki_article"
        source.setdefault("provenance", {})["source_signal_classes"] = ["wiki_article"]

    persist_fact_intake_payload(conn, payload)
    
    workbench = build_fact_review_workbench_payload(conn, run_id=payload["run"]["run_id"])
    
    # Check "vandalism" signal
    vandal_fact = next(row for row in workbench["facts"] if "vandalism" in row["canonical_label"].lower() or "vandal" in row["canonical_label"].lower())
    assert "volatility_signal" in vandal_fact["signal_classes"]
    assert "volatility_signal" in vandal_fact["inferred_signal_classes"]
    
    # Check "disputed" signal
    dispute_fact = next(row for row in workbench["facts"] if "disputed" in row["canonical_label"].lower() or "dispute" in row["canonical_label"].lower())
    assert "volatility_signal" in dispute_fact["signal_classes"]
    assert "volatility_signal" in dispute_fact["inferred_signal_classes"]

    # Check "warning" and "unsourced" signal
    # "warning" is an administrative_edit, "unsourced" is a volatility_signal
    admin_fact = next(row for row in workbench["facts"] if "warning" in row["canonical_label"].lower())
    # Note: "unsourced" should trigger volatility_signal
    # But wait, does the lexical analysis pick up all tokens? Yes.
    assert "volatility_signal" in admin_fact["signal_classes"]
    assert "volatility_signal" in admin_fact["inferred_signal_classes"]
    
    assert workbench["zelph"]["inferred_fact_count"] >= 3
    assert workbench["zelph"]["rule_status"] == "engine_ok"

def test_zelph_identifies_contested_and_unverified_as_volatility_signals() -> None:
    conn = sqlite3.connect(":memory:")
    units = [
        TextUnit(
            unit_id="unit:contest",
            source_id="wiki-contest",
            source_type="wiki_article",
            text="Revision by Editor3: Contested claim removed.",
        ),
        TextUnit(
            unit_id="unit:unverify",
            source_id="wiki-unverify",
            source_type="wiki_article",
            text="Revision by Editor4: Unverified information; needs citation.",
        ),
    ]
    payload = build_fact_intake_payload_from_text_units(units, source_label="zelph_volatility_test_2")
    
    for source in payload["sources"]:
        source["source_type"] = "wiki_article"
        source.setdefault("provenance", {})["source_signal_classes"] = ["wiki_article"]

    persist_fact_intake_payload(conn, payload)
    
    workbench = build_fact_review_workbench_payload(conn, run_id=payload["run"]["run_id"])
    
    contest_fact = next(row for row in workbench["facts"] if "contested" in row["canonical_label"].lower())
    assert "volatility_signal" in contest_fact["signal_classes"]
    
    unverify_fact = next(row for row in workbench["facts"] if "unverified" in row["canonical_label"].lower())
    assert "volatility_signal" in unverify_fact["signal_classes"]

def test_zelph_flags_reversion_without_context_as_risk() -> None:
    conn = sqlite3.connect(":memory:")
    units = [
        TextUnit(
            unit_id="unit:rev_no_context",
            source_id="wiki-rev",
            source_type="wiki_article",
            text="Revision by E1: Reverted change.",
        ),
        TextUnit(
            unit_id="unit:rev_with_context",
            source_id="wiki-rev",
            source_type="wiki_article",
            text="Revision by E2: Reverted change because it was unsourced.",
        ),
    ]
    payload = build_fact_intake_payload_from_text_units(units, source_label="zelph_rev_test")
    
    for source in payload["sources"]:
        source["source_type"] = "wiki_article"
        source.setdefault("provenance", {})["source_signal_classes"] = ["wiki_article"]

    persist_fact_intake_payload(conn, payload)
    
    workbench = build_fact_review_workbench_payload(conn, run_id=payload["run"]["run_id"])
    
    # Check no-context revision
    rev_no_context_fact = next(row for row in workbench["facts"] if "e1" in row["canonical_label"].lower())
    assert "volatility_signal" in rev_no_context_fact["signal_classes"]
    
    # Verify the "risk_signal" was inferred by Zelph
    # Note: inferred triples are in workbench["zelph"]["triples"]
    triples = workbench["zelph"]["triples"]
    print(f"DEBUG: ALL TRIPLES: {json.dumps(triples, indent=2)}")
    
    # Check for is_reversion first
    is_rev_found = any(t["predicate"] == "is_reversion" for t in triples)
    print(f"DEBUG: is_reversion found: {is_rev_found}")

    # Find risk_signal for rev_no_context_fact
    risk_found = any(
        t["predicate"] == "signal_class" and t["object"] == "Reversion without context"
        for t in triples
    )
    assert risk_found, f"Should have flagged lack of context as a risk. Triples: {json.dumps(triples)}"
    
    # Check with-context revision
    rev_with_context_fact = next(row for row in workbench["facts"] if "e2" in row["canonical_label"].lower())
    assert "volatility_signal" in rev_with_context_fact["signal_classes"]
    
    # Verify the "risk_signal" was NOT inferred for E2 (who gave context)
    node_id_e2 = "fact_" + str(rev_with_context_fact["fact_id"]).replace(':', '_').replace('-', '_')
    risk_for_e2 = any(
        t["subject"] == node_id_e2 and t["predicate"] == "signal_class" and t["object"] == "Reversion without context"
        for t in triples
    )
    assert not risk_for_e2, f"Should NOT have flagged reversion with context as a risk, but found: {triples}"
