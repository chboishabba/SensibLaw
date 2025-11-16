"""Documents tab for the SensibLaw Streamlit console."""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

import streamlit as st

try:  # Optional dependency for tabular display
    import pandas as pd
except Exception:  # pragma: no cover - pandas is optional at runtime
    pd = None  # type: ignore[assignment]

try:  # Optional dependency for graph visualisations
    import altair as alt
except Exception:  # pragma: no cover - altair is optional at runtime
    alt = None  # type: ignore[assignment]

from sensiblaw_streamlit.constants import DEFAULT_DB_NAME
from sensiblaw_streamlit.document_preview import (
    collect_document_actor_summary,
    render_document_preview,
)
from sensiblaw_streamlit.shared import (
    ROOT,
    _build_knowledge_graph_dot,
    _download_json,
    _ensure_parent,
    _render_dot,
    _write_bytes,
)
from sensiblaw_streamlit.tabs.knowledge_graph import _load_graph_from_store

from src.api.routes import _graph as ROUTES_GRAPH
from src.models.document import Document
from src.pdf_ingest import iter_process_pdf, process_pdf
from src.storage.versioned_store import VersionedStore


def _format_join(values: List[str], separator: str = ", ") -> str:
    return separator.join(values) if values else ""


@dataclass
class PDFIngestStepper:
    """Track interactive ingestion state for step-by-step debugging."""

    generator: Iterator[Tuple[str, Dict[str, Any]]]
    tmp_dir: Path
    pdf_path: Path
    source_name: Optional[str]
    log: List[Tuple[str, Dict[str, Any]]] = field(default_factory=list)
    completed: bool = False
    document_rendered: bool = False

    def step(self) -> Tuple[str, Dict[str, Any]]:
        stage, payload = next(self.generator)
        self.log.append((stage, payload))
        if stage == "save":
            self.completed = True
        return stage, payload

    def close(self) -> None:
        try:
            self.generator.close()
        except Exception:  # pragma: no cover - defensive cleanup
            pass
        shutil.rmtree(self.tmp_dir, ignore_errors=True)


def _render_actor_summary(document: Document) -> None:
    actors = collect_document_actor_summary(document)
    if not actors:
        st.info("No actors were detected in the extracted rules.")
        return

    st.markdown("### Actors detected in structured rules")
    rows = []
    for summary in actors:
        rows.append(
            {
                "Actor": summary.actor,
                "Mentions": summary.occurrences,
                "Modalities": _format_join(summary.modalities),
                "Sample actions": _format_join(summary.actions, separator="; "),
                "Sections": _format_join(summary.sections, separator="; "),
                "Aliases": _format_join(summary.aliases),
            }
        )

    if pd is not None:
        frame = pd.DataFrame(rows)
        st.dataframe(frame, use_container_width=True)
    else:  # pragma: no cover - fallback when pandas is unavailable
        st.table(rows)


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

    last_document = st.session_state.get("last_document_payload")
    last_metadata = None
    if isinstance(last_document, dict):
        last_metadata = last_document.get("metadata")

    def _default_metadata_value(key: str, fallback: str = "") -> str:
        state_key = f"document_form_{key}"
        if state_key in st.session_state:
            stored_value = st.session_state[state_key]
            if stored_value:
                return stored_value
            if stored_value == "":
                return ""
        if isinstance(last_metadata, dict):
            value = last_metadata.get(key)
            if value:
                if key == "cultural_flags" and isinstance(value, list):
                    return ", ".join(value)
                return value
            if key == "cultural_flags" and value == []:
                return ""
        return fallback

    def _enum_value(value: Any) -> str:
        if hasattr(value, "value"):
            return str(value.value)
        if isinstance(value, str):
            return value
        return str(value)

    def _refresh_graph_with_document(
        document: Document, *, db_path: Path, stored_id: Optional[int]
    ) -> None:
        """Reload the shared graph and render a preview for ``document``."""

        st.session_state["kg_graph_store_path"] = str(db_path)

        try:
            node_count, edge_count, primary_seed = _load_graph_from_store(db_path)
        except (FileNotFoundError, ValueError) as exc:
            st.warning(f"Knowledge graph refresh skipped: {exc}")
            return

        st.info(
            f"Knowledge graph refreshed with {node_count} nodes and {edge_count} edges."
        )

        if primary_seed:
            st.session_state["kg_subgraph_seed_input"] = primary_seed
            st.session_state["kg_case_id_input"] = primary_seed
            st.session_state["kg_subgraph_seed_select"] = primary_seed

        doc_identifier = (
            (document.metadata.canonical_id or "").strip()
            or (document.metadata.citation or "").strip()
            or (f"Document#{stored_id}" if stored_id is not None else "")
        )
        if not doc_identifier:
            doc_identifier = document.metadata.title or "Document"
        doc_identifier = str(doc_identifier)
        doc_prefix = f"{doc_identifier}::"

        nodes_payload: List[Dict[str, Any]] = []
        for identifier, node in ROUTES_GRAPH.nodes.items():
            if identifier == doc_identifier or identifier.startswith(doc_prefix):
                node_payload = asdict(node)
                nodes_payload.append(node_payload)

        if not nodes_payload:
            st.info("No knowledge graph nodes were generated for this document yet.")
            return

        st.session_state["kg_subgraph_seed_input"] = doc_identifier
        st.session_state["kg_subgraph_seed_select"] = doc_identifier
        st.session_state["kg_case_id_input"] = doc_identifier

        edges_payload: List[Dict[str, Any]] = []
        for edge in ROUTES_GRAPH.edges:
            if (
                edge.source == doc_identifier
                or edge.target == doc_identifier
                or edge.source.startswith(doc_prefix)
                or edge.target.startswith(doc_prefix)
            ):
                edges_payload.append(asdict(edge))

        st.markdown("### Knowledge graph preview")

        graph_payload = {"nodes": nodes_payload, "edges": edges_payload}
        dot = _build_knowledge_graph_dot(graph_payload)
        if dot:
            _render_dot(dot, key="document_knowledge_graph")
            return

        if alt is not None and pd is not None:
            node_records: List[Dict[str, Any]] = []
            for node in nodes_payload:
                metadata = node.get("metadata") or {}
                node_records.append(
                    {
                        "identifier": node.get("identifier"),
                        "type": _enum_value(node.get("type")),
                        "title": metadata.get("title")
                        or metadata.get("heading")
                        or node.get("identifier"),
                        "jurisdiction": metadata.get("jurisdiction"),
                        "citation": metadata.get("citation"),
                    }
                )

            type_order = {
                type_name: index
                for index, type_name in enumerate(
                    sorted({record["type"] for record in node_records})
                )
            }

            for index, record in enumerate(node_records):
                record["x"] = float(index)
                record["y"] = float(type_order.get(record["type"], 0))

            node_frame = pd.DataFrame(node_records)
            node_position = {
                record["identifier"]: (record["x"], record["y"])
                for record in node_records
            }

            edge_records: List[Dict[str, Any]] = []
            for edge in edges_payload:
                source_pos = node_position.get(edge.get("source"))
                target_pos = node_position.get(edge.get("target"))
                if not source_pos or not target_pos:
                    continue
                edge_records.append(
                    {
                        "type": _enum_value(edge.get("type")),
                        "x": source_pos[0],
                        "y": source_pos[1],
                        "x2": target_pos[0],
                        "y2": target_pos[1],
                    }
                )

            chart = None
            if edge_records:
                edge_frame = pd.DataFrame(edge_records)
                chart = alt.Chart(edge_frame).mark_rule(opacity=0.5).encode(
                    x="x:Q",
                    x2="x2:Q",
                    y="y:Q",
                    y2="y2:Q",
                    color=alt.Color("type:N", title="Edge type"),
                )

            node_chart = alt.Chart(node_frame).mark_circle(size=240).encode(
                x="x:Q",
                y="y:Q",
                color=alt.Color("type:N", title="Node type"),
                tooltip=["identifier", "title", "type", "jurisdiction", "citation"],
            )

            label_chart = alt.Chart(node_frame).mark_text(dy=-14).encode(
                x="x:Q",
                y="y:Q",
                text="title:N",
            )

            combined = node_chart + label_chart
            if chart is not None:
                combined = chart + combined

            combined = combined.properties(
                height=max(240, 80 * max(1, len(type_order))), width=700
            ).configure_axis(
                title=None,
                ticks=False,
                labels=False,
                domain=False,
            )

            st.altair_chart(combined, use_container_width=True)
            return

        st.warning(
            "Graph visualisation is unavailable. Install graphviz or altair+pandas to enable previews."
        )

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
        title = st.text_input("Title", value=_default_metadata_value("title", ""))
        jurisdiction = st.text_input(
            "Jurisdiction",
            value=_default_metadata_value("jurisdiction", ""),
        )
        citation = st.text_input(
            "Citation", value=_default_metadata_value("citation", "")
        )
        cultural_flags = st.text_input(
            "Cultural flags (comma separated)",
            value=_default_metadata_value("cultural_flags", ""),
        )
        step_processing = st.toggle(
            "Step ingestion like a debugger",
            value=st.session_state.get("pdf_step_processing", False),
            help=(
                "Enable manual stepping through extraction, parsing, persistence, and "
                "saving. Useful for debugging long PDFs."
            ),
        )
        st.session_state["pdf_step_processing"] = step_processing
        breakpoint_chars: Optional[int] = None
        if step_processing:
            breakpoint_chars = st.number_input(
                "Breakpoint after N characters",
                min_value=0,
                step=500,
                value=st.session_state.get("pdf_step_breakpoint", 0),
                help=(
                    "Pause extraction once the running character count crosses this "
                    "threshold."
                ),
            )
            st.session_state["pdf_step_breakpoint"] = breakpoint_chars
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
            flags = [f.strip() for f in cultural_flags.split(",") if f.strip()]
            if step_processing:
                st.info(
                    "Stepper armed. Use the debugger controls below to walk through ingestion."
                )
                tmp_dir = Path(tempfile.mkdtemp(prefix="sensiblaw_pdf_"))
                pdf_path = _write_bytes(
                    tmp_dir / (source_name or "document.pdf"), buffer
                )
                generator = iter_process_pdf(
                    pdf_path,
                    jurisdiction=jurisdiction or None,
                    citation=citation or None,
                    title=title or None,
                    cultural_flags=flags or None,
                    db_path=db_path,
                    break_after_chars=(
                        int(breakpoint_chars)
                        if breakpoint_chars and int(breakpoint_chars) > 0
                        else None
                    ),
                )
                existing_stepper: Optional[PDFIngestStepper] = st.session_state.get(
                    "pdf_stepper"
                )
                if existing_stepper:
                    existing_stepper.close()
                st.session_state["pdf_stepper"] = PDFIngestStepper(
                    generator=generator,
                    tmp_dir=tmp_dir,
                    pdf_path=pdf_path,
                    source_name=source_name,
                )
            else:
                st.info(f"Processing {source_name} …")
                with st.spinner("Extracting text and rules"):
                    tmp_dir = Path(tempfile.mkdtemp(prefix="sensiblaw_pdf_"))
                    pdf_path = _write_bytes(
                        tmp_dir / (source_name or "document.pdf"), buffer
                    )
                    document, stored_id = process_pdf(
                        pdf_path,
                        jurisdiction=jurisdiction or None,
                        citation=citation or None,
                        title=title or None,
                        cultural_flags=flags or None,
                        db_path=db_path,
                    )
                _handle_processed_document(
                    document, stored_id=stored_id, db_path=db_path
                )
                shutil.rmtree(tmp_dir, ignore_errors=True)

    _render_stepper_panel(db_path)
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


def _handle_processed_document(
    document: Document, *, stored_id: Optional[int], db_path: Path
) -> None:
    st.success("PDF processed successfully.")
    st.markdown("### Document preview")
    render_document_preview(document)
    _render_actor_summary(document)
    doc_payload = document.to_dict()
    st.session_state["document_form_jurisdiction"] = (
        document.metadata.jurisdiction or ""
    )
    st.session_state["document_form_citation"] = document.metadata.citation or ""
    st.session_state["document_form_title"] = document.metadata.title or ""
    st.session_state["document_form_cultural_flags"] = ", ".join(
        document.metadata.cultural_flags or []
    )
    if stored_id is not None:
        st.info(f"Stored as document ID {stored_id} in {db_path}")
        doc_payload["doc_id"] = stored_id
    st.session_state["last_document_payload"] = doc_payload
    st.session_state["expand_last_document"] = True
    _refresh_graph_with_document(document, db_path=db_path, stored_id=stored_id)


def _display_step_log(
    stage: str,
    payload: Dict[str, Any],
    *,
    stepper: PDFIngestStepper,
    db_path: Path,
) -> None:
    if stage == "extraction":
        char_count = payload.get("char_count", 0)
        pages = payload.get("pages") or []
        complete = payload.get("complete", False)
        breakpoint_chars = payload.get("breakpoint")
        summary = (
            f"Extracted {len(pages)} page(s) / {char_count} characters."
        )
        if breakpoint_chars and not complete:
            summary += (
                f" Breakpoint hit after {breakpoint_chars} characters."
                " Step again to continue extraction."
            )
        st.info(summary)
    elif stage == "build":
        document: Optional[Document] = payload.get("document")
        if isinstance(document, Document):
            st.success(
                "Structured document built with "
                f"{len(document.provisions)} provisions and "
                f"{len(document.toc_entries)} TOC entries."
            )
    elif stage == "persist":
        stored_id = payload.get("stored_doc_id")
        if stored_id is not None:
            st.info(f"Persisted revision as document ID {stored_id}.")
    elif stage == "save":
        output_path = payload.get("output_path")
        if output_path:
            st.success(f"Saved document JSON to {output_path}")
        document = payload.get("document")
        if isinstance(document, Document) and not stepper.document_rendered:
            stored_id = payload.get("stored_doc_id")
            _handle_processed_document(document, stored_id=stored_id, db_path=db_path)
            stepper.document_rendered = True


def _render_stepper_panel(db_path: Path) -> None:
    stepper: Optional[PDFIngestStepper] = st.session_state.get("pdf_stepper")
    if not stepper:
        return

    st.markdown("### Ingestion debugger")
    if not stepper.log:
        st.info(
            "Stepper initialised. Use the controls below to advance the ingestion pipeline."
        )
    else:
        for stage, payload in stepper.log:
            _display_step_log(stage, payload, stepper=stepper, db_path=db_path)

    controls = st.columns(3)
    if not stepper.completed:
        with controls[0]:
            if st.button("Run next step", key="pdf_stepper_next"):
                try:
                    stage, payload = stepper.step()
                except StopIteration:
                    stepper.completed = True
                else:
                    _display_step_log(stage, payload, stepper=stepper, db_path=db_path)
        with controls[1]:
            if st.button("Abort stepping", key="pdf_stepper_abort"):
                stepper.close()
                st.session_state.pop("pdf_stepper", None)
                st.warning("Stepping aborted and state cleared.")
                return
    else:
        st.success("Ingestion pipeline completed.")

    with controls[2]:
        if st.button("Clear debugger", key="pdf_stepper_clear"):
            stepper.close()
            st.session_state.pop("pdf_stepper", None)
            st.info("Stepper cleared.")


__all__ = ["render"]
