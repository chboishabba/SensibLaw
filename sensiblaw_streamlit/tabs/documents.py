"""Documents tab for the SensibLaw Streamlit console."""

from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path

import streamlit as st

from sensiblaw_streamlit.constants import DEFAULT_DB_NAME
from sensiblaw_streamlit.document_preview import render_document_preview
from sensiblaw_streamlit.shared import (
    ROOT,
    _download_json,
    _ensure_parent,
    _write_bytes,
)

from src.models.document import Document
from src.pdf_ingest import process_pdf
from src.storage.versioned_store import VersionedStore


def render() -> None:
    st.subheader("Documents")
    st.write(
        "Ingest PDFs, persist revisions via the versioned store, and inspect historical snapshots."
    )

    default_store = st.session_state.get(
        "document_store_path",
        str(ROOT / "ui" / DEFAULT_DB_NAME),
    )
    store_path_input = st.text_input(
        "SQLite store path",
        value=default_store,
        help="Document revisions are persisted to this SQLite database.",
    )
    st.session_state["document_store_path"] = store_path_input
    db_path = Path(store_path_input).expanduser()
    _ensure_parent(db_path)

    with st.form("pdf_ingest_form"):
        st.markdown("### PDF ingestion")
        sample_pdf = None
        pdf_files = list(ROOT.glob("*.pdf"))
        if pdf_files:
            sample_pdf = st.selectbox(
                "Sample PDF", ["-- None --"] + [p.name for p in pdf_files], index=0
            )
        uploaded_pdf = st.file_uploader(
            "Upload PDF for processing", type=["pdf"], key="pdf_uploader"
        )
        jurisdiction = st.text_input("Jurisdiction", value="High Court of Australia")
        citation = st.text_input("Citation", value="[1992] HCA 23")
        cultural_flags = st.text_input("Cultural flags (comma separated)", value="")
        ingest = st.form_submit_button("Process PDF")

    if ingest:
        buffer = None
        source_name = None
        if uploaded_pdf is not None:
            buffer = uploaded_pdf.getvalue()
            source_name = uploaded_pdf.name
        elif sample_pdf and sample_pdf != "-- None --":
            buffer = (ROOT / sample_pdf).read_bytes()
            source_name = sample_pdf
        else:
            st.error("Please upload a PDF or choose a sample file.")

        if buffer:
            st.info(f"Processing {source_name} …")
            with st.spinner("Extracting text and rules"):
                tmp_dir = Path(tempfile.mkdtemp(prefix="sensiblaw_pdf_"))
                pdf_path = _write_bytes(
                    tmp_dir / (source_name or "document.pdf"), buffer
                )
                flags = [f.strip() for f in cultural_flags.split(",") if f.strip()]
                document, stored_id = process_pdf(
                    pdf_path,
                    jurisdiction=jurisdiction or None,
                    citation=citation or None,
                    cultural_flags=flags or None,
                    db_path=db_path,
                )
            st.success("PDF processed successfully.")
            st.markdown("### Document preview")
            render_document_preview(document)
            doc_payload = document.to_dict()
            if stored_id is not None:
                st.info(f"Stored as document ID {stored_id} in {db_path}")
                doc_payload["doc_id"] = stored_id
            st.session_state["last_document_payload"] = doc_payload
            st.session_state["expand_last_document"] = True

    last_document = st.session_state.get("last_document_payload")
    if last_document:
        expanded = st.session_state.pop("expand_last_document", False)
        with st.expander("Most recent document metadata and rules", expanded=expanded):
            st.json(last_document)
        _download_json(
            "Download document JSON",
            last_document,
            "document.json",
            key="download_document_json",
        )

    st.markdown("### Snapshot lookup")
    with st.form("snapshot_form"):
        doc_id = st.number_input("Document ID", min_value=1, step=1, value=1)
        as_at = st.date_input("Snapshot date", value=date.today())
        fetch = st.form_submit_button("Fetch snapshot")

    if fetch:
        with st.spinner("Loading document snapshot"):
            store = VersionedStore(db_path)
            try:
                snapshot = store.snapshot(int(doc_id), as_at)
            finally:
                store.close()
        if snapshot is None:
            st.warning("No revision found for the supplied ID and date.")
        else:
            payload = snapshot.to_dict() if isinstance(snapshot, Document) else snapshot
            with st.expander("Snapshot contents", expanded=True):
                st.json(payload)
            _download_json("Download snapshot JSON", payload, "snapshot.json")


__all__ = ["render"]
