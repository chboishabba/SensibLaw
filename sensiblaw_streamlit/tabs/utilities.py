"""Utilities tab for the SensibLaw Streamlit console."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from sensiblaw_streamlit.constants import SAMPLE_FRL_PAYLOAD
from sensiblaw_streamlit.shared import _download_json

from src.glossary.service import lookup as glossary_lookup
from src.frame.compiler import compile_frame
from src.receipts.build import build_receipt
from src.receipts.verify import verify_receipt
from src.text.similarity import simhash
from src.ingestion.frl import fetch_acts
from src.rules import Rule
from src.rules.reasoner import check_rules
from src.harm.index import compute_harm
from src.reports.research_health import compute_research_health


def render() -> None:
    st.subheader("Utilities")
    st.write(
        "Quick access to glossary lookups, frame compilation, receipts, similarity fingerprints, FRL ingestion, rule checks, and harm scores."
    )
    st.info(
        "Labs surface: not covered by Sprint 9 invariants; tools here are demo-only and read-only."
    )

    st.markdown("### Glossary lookup")
    with st.form("glossary_form"):
        term = st.text_input("Term", value="permanent stay")
        lookup_submit = st.form_submit_button("Lookup")
    if lookup_submit:
        entry = glossary_lookup(term)
        if entry is None:
            st.warning("No glossary entry found.")
        else:
            st.json(
                {"phrase": entry.phrase, "text": entry.text, "metadata": entry.metadata}
            )

    st.markdown("### Frame compiler")
    with st.form("frame_form"):
        frame_source = st.text_area(
            "Frame definition", "actor must consider community impacts"
        )
        frame_submit = st.form_submit_button("Compile frame")
    if frame_submit:
        compiled = compile_frame(frame_source)
        st.code(compiled)

    st.markdown("### Receipts")
    with st.form("receipt_form"):
        receipt_input = st.text_area(
            "Receipt payload (JSON)",
            value=json.dumps({"actor": "court", "action": "issued order"}, indent=2),
            height=160,
        )
        receipt_submit = st.form_submit_button("Build & verify")
    if receipt_submit:
        try:
            payload = json.loads(receipt_input or "{}")
        except json.JSONDecodeError as exc:
            st.error(f"Invalid JSON: {exc}")
        else:
            built = build_receipt(payload)
            valid = verify_receipt(built)
            st.json({"receipt": built, "verified": valid})
            _download_json("Download receipt", built, "receipt.json")

    st.markdown("### Text similarity")
    with st.form("simhash_form"):
        simhash_text = st.text_area(
            "Text", "Sample text for simhash fingerprint", height=120
        )
        simhash_submit = st.form_submit_button("Compute simhash")
    if simhash_submit:
        fingerprint = simhash(simhash_text)
        st.code(fingerprint)

    st.markdown("### FRL ingestion")
    with st.form("frl_form"):
        frl_json = st.text_area(
            "FRL payload (JSON)",
            value=json.dumps(SAMPLE_FRL_PAYLOAD, indent=2),
            height=220,
        )
        frl_submit = st.form_submit_button("Build graph from payload")
    if frl_submit:
        try:
            data = json.loads(frl_json or "{}")
        except json.JSONDecodeError as exc:
            st.error(f"Invalid JSON: {exc}")
        else:
            with st.spinner("Constructing graph"):
                nodes, edges = fetch_acts("http://example.com", data=data)
            st.json({"nodes": nodes, "edges": edges})
            _download_json("Download FRL nodes", nodes, "frl_nodes.json")
            _download_json("Download FRL edges", edges, "frl_edges.json")

    st.markdown("### Rule consistency")
    with st.form("rules_form"):
        rules_json = st.text_area(
            "Rules (JSON list)",
            value=json.dumps(
                [
                    {"actor": "court", "modality": "must", "action": "hear the matter"},
                    {
                        "actor": "court",
                        "modality": "must not",
                        "action": "hear the matter",
                    },
                ],
                indent=2,
            ),
            height=200,
        )
        rules_submit = st.form_submit_button("Check rules")
    if rules_submit:
        try:
            rule_payload = json.loads(rules_json or "[]")
        except json.JSONDecodeError as exc:
            st.error(f"Invalid JSON: {exc}")
        else:
            rules = [Rule(**item) for item in rule_payload]
            issues = check_rules(rules)
            st.json({"issues": issues})

    st.markdown("### Harm scoring")
    with st.form("harm_form"):
        harm_story = st.text_area(
            "Story metrics (JSON)",
            value=json.dumps(
                {
                    "lost_evidence_items": 2,
                    "delay_months": 18,
                    "flags": ["vulnerable_witness"],
                },
                indent=2,
            ),
            height=200,
        )
        harm_submit = st.form_submit_button("Compute harm score")
    if harm_submit:
        try:
            story = json.loads(harm_story or "{}")
        except json.JSONDecodeError as exc:
            st.error(f"Invalid JSON: {exc}")
        else:
            score = compute_harm(story)
            st.json(score)
            _download_json("Download harm score", score, "harm_score.json")

    st.markdown("### Research health")
    default_db = str(Path("ui") / "sensiblaw_documents.sqlite")
    db_path = st.text_input("SQLite store path", value=default_db)
    if st.button("Compute research-health report"):
        db_file = Path(db_path).expanduser()
        if not db_file.exists():
            st.error(f"Database not found at {db_file}")
        else:
            report = compute_research_health(db_file).to_dict()
            st.success("Report computed")
            st.json(report)
            st.caption(
                "Includes tokens_per_document_mean to monitor compression and growth invariants."
            )


__all__ = ["render"]
