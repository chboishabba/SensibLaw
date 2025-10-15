"""SensibLaw Streamlit operations console."""

from __future__ import annotations

import json
import re
import sys
import tempfile
from dataclasses import asdict, is_dataclass
from datetime import date
from enum import Enum
from html import escape
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import streamlit as st
import streamlit.components.v1 as components

try:  # Optional dependency for tabular display
    import pandas as pd
except Exception:  # pragma: no cover - pandas is optional at runtime
    pd = None  # type: ignore[assignment]

# Ensure the project source tree is importable when running ``streamlit run``.
ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from api.routes import (  # noqa: E402  - imported after path adjustment
    HTTPException,
    execute_tests,
    fetch_case_treatment,
    fetch_provision_atoms,
    generate_subgraph,
    _graph as ROUTES_GRAPH,
)
from api.sample_routes import api_provision, api_subgraph, api_treatment  # noqa: E402
from concepts.cloud import build_cloud as advanced_cloud  # noqa: E402
from distinguish.engine import compare_story_to_case  # noqa: E402
from distinguish.loader import load_case_silhouette  # noqa: E402
from frame.compiler import compile_frame  # noqa: E402
from glossary.service import lookup as glossary_lookup  # noqa: E402
from graph.models import EdgeType, GraphEdge, GraphNode, NodeType  # noqa: E402
from harm.index import compute_harm  # noqa: E402
from ingestion.frl import fetch_acts  # noqa: E402
from models.document import Document, DocumentTOCEntry  # noqa: E402
from models.provision import Provision  # noqa: E402
from pipeline import build_cloud, match_concepts, normalise  # noqa: E402
from pdf_ingest import process_pdf  # noqa: E402
from receipts.build import build_receipt  # noqa: E402
from receipts.verify import verify_receipt  # noqa: E402
from rules import Rule  # noqa: E402
from rules.extractor import extract_rules  # noqa: E402
from rules.reasoner import check_rules  # noqa: E402
from storage.versioned_store import VersionedStore  # noqa: E402
from tests.templates import TEMPLATE_REGISTRY  # noqa: E402
from text.similarity import simhash  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers and constants
# ---------------------------------------------------------------------------

SAMPLE_CASES: Dict[str, str] = {"GLJ Permanent Stay": "glj"}
SAMPLE_STORY_FACTS = {
    "facts": {
        "delay": True,
        "abuse_of_process": True,
        "fair_trial_possible": False,
    }
}
SAMPLE_FRL_PAYLOAD = {
    "results": [
        {
            "id": "Act1",
            "title": "Sample Act",
            "sections": [
                {
                    "number": "1",
                    "title": "Definitions",
                    "body": '"Dog" means a domesticated animal.',
                },
                {
                    "number": "2",
                    "title": "Care",
                    "body": "A person must care for their dog. See section 1.",
                },
            ],
        }
    ]
}
SAMPLE_GRAPH_CASES = {
    "Case#Mabo1992": {
        "title": "Mabo v Queensland (No 2)",
        "court": "HCA",
        "consent_required": False,
    },
    "Case#Wik1996": {
        "title": "Wik Peoples v Queensland",
        "court": "HCA",
        "consent_required": False,
    },
    "Case#Ward2002": {
        "title": "Western Australia v Ward",
        "court": "HCA",
        "consent_required": True,
        "cultural_flags": ["sacred_information"],
    },
}
SAMPLE_GRAPH_EDGES = [
    (
        "Case#Mabo1992",
        "Case#Wik1996",
        "followed",
        3.0,
    ),
    (
        "Case#Mabo1992",
        "Case#Ward2002",
        "distinguished",
        1.0,
    ),
    (
        "Case#Wik1996",
        "Case#Ward2002",
        "followed",
        2.0,
    ),
]
SAMPLE_CASE_TREATMENT_METADATA = {
    "followed": {"court": "HCA"},
    "distinguished": {"court": "FCA"},
}
DEFAULT_DB_NAME = "sensiblaw_documents.sqlite"


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _write_bytes(path: Path, data: bytes) -> Path:
    _ensure_parent(path)
    path.write_bytes(data)
    return path


def _json_default(value: Any) -> Any:
    """Provide JSON-serialisation fallbacks for complex objects."""

    if isinstance(value, Enum):
        return value.value
    if isinstance(value, date):
        return value.isoformat()
    if is_dataclass(value):
        return asdict(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serialisable")


def _download_json(label: str, payload: Any, filename: str) -> None:
    st.download_button(
        label,
        json.dumps(payload, indent=2, ensure_ascii=False, default=_json_default),
        file_name=filename,
        mime="application/json",
    )


def _normalise_anchor_key(value: Optional[str]) -> Optional[str]:
    """Return a slug suitable for anchor lookup."""

    if not value:
        return None
    slug = re.sub(r"[^0-9a-zA-Z]+", "-", value).strip("-").lower()
    return slug or None


def _collect_provisions(
    provisions: List[Provision],
) -> Tuple[List[Tuple[Provision, str]], Dict[str, str]]:
    """Assign anchor IDs to provisions and build lookup keys."""

    anchors: List[Tuple[Provision, str]] = []
    anchor_lookup: Dict[str, str] = {}

    def register(key: Optional[str], anchor: str) -> None:
        normalised = _normalise_anchor_key(key)
        if normalised and normalised not in anchor_lookup:
            anchor_lookup[normalised] = anchor

    counter = 0

    def walk(node: Provision) -> None:
        nonlocal counter
        counter += 1
        anchor = f"segment-{counter}"
        anchors.append((node, anchor))
        register(node.identifier, anchor)
        register(node.heading, anchor)
        register(node.stable_id, anchor)
        if node.toc_id is not None:
            register(str(node.toc_id), anchor)
            register(f"toc-{node.toc_id}", anchor)
        for child in node.children:
            walk(child)

    for provision in provisions:
        walk(provision)
    return anchors, anchor_lookup


def _render_toc(entries: List[DocumentTOCEntry], lookup: Dict[str, str]) -> str:
    """Render nested table-of-contents entries as HTML."""

    if not entries:
        return "<p class='toc-empty'>No table of contents entries detected.</p>"

    def render_nodes(nodes: List[DocumentTOCEntry]) -> str:
        items: List[str] = []
        for entry in nodes:
            label_parts: List[str] = []
            if entry.identifier:
                label_parts.append(escape(entry.identifier))
            if entry.title:
                label_parts.append(escape(entry.title))
            label = " ".join(label_parts) or escape(entry.node_type or "Entry")
            anchor: Optional[str] = None
            for key in (
                entry.identifier,
                entry.title,
                f"{entry.identifier} {entry.title}"
                if entry.identifier and entry.title
                else None,
                f"toc-{entry.identifier}" if entry.identifier else None,
            ):
                normalised = _normalise_anchor_key(key) if key else None
                if normalised and normalised in lookup:
                    anchor = lookup[normalised]
                    break
            child_html = render_nodes(entry.children) if entry.children else ""
            if anchor:
                item = f"<li><a href='#{anchor}'>{label}</a>{child_html}</li>"
            else:
                item = f"<li>{label}{child_html}</li>"
            items.append(item)
        return f"<ul>{''.join(items)}</ul>"

    return f"<nav class='toc-tree'>{render_nodes(entries)}</nav>"


def _render_atom_badges(provision: Provision) -> str:
    """Render interactive rule atom badges for a provision."""

    if not provision.rule_atoms:
        return ""

    badges: List[str] = []
    for index, atom in enumerate(provision.rule_atoms, start=1):
        detail_dict = atom.to_dict()
        detail_json = json.dumps(detail_dict, indent=2, ensure_ascii=False)
        detail_attr = escape(detail_json, quote=True)
        label_source = atom.atom_type or atom.role or f"Atom {index}"
        label = escape(label_source)
        badges.append(
            (
                "<span class='atom-badge' tabindex='0' data-label='"
                f"{label}' data-detail='{detail_attr}'>{label}</span>"
            )
        )

    return (
        "<div class='atom-badges'><strong>Atoms:</strong> "
        + " ".join(badges)
        + "</div>"
    )


def _render_provision_section(provision: Provision, anchor: str) -> str:
    """Render a single provision, including text and atoms."""

    heading = escape(provision.heading) if provision.heading else "Provision"
    identifier = escape(provision.identifier) if provision.identifier else ""
    metadata_parts = []
    if identifier:
        metadata_parts.append(f"<span class='provision-identifier'>{identifier}</span>")
    if provision.toc_id is not None:
        metadata_parts.append(
            f"<span class='provision-toc'>TOC ID {escape(str(provision.toc_id))}</span>"
        )
    if provision.cultural_flags:
        flags = ", ".join(escape(flag) for flag in provision.cultural_flags)
        metadata_parts.append(f"<span class='provision-flags'>{flags}</span>")

    metadata_html = (
        "<div class='provision-meta'>" + " • ".join(metadata_parts) + "</div>"
        if metadata_parts
        else ""
    )

    paragraphs = [
        f"<p>{escape(line.strip())}</p>"
        for line in provision.text.splitlines()
        if line.strip()
    ]
    atom_html = _render_atom_badges(provision)
    return (
        f"<section class='provision-section' id='{anchor}' data-anchor='{anchor}'>"
        f"<h4>{heading}</h4>{metadata_html}{''.join(paragraphs)}{atom_html}</section>"
    )


def build_document_preview_html(document: Document) -> str:
    """Generate HTML preview for a processed document."""

    provision_sections, lookup = _collect_provisions(document.provisions)
    toc_html = _render_toc(document.toc_entries, lookup)

    if provision_sections:
        sections_html = "".join(
            _render_provision_section(provision, anchor)
            for provision, anchor in provision_sections
        )
    else:
        sections_html = "<p class='no-provisions'>No provisions were extracted.</p>"

    stylesheet = """
<style>
.document-preview {
    font-family: var(--font, "Source Sans Pro", sans-serif);
    display: flex;
    flex-direction: column;
    gap: 1rem;
}
.document-preview .document-columns {
    display: grid;
    grid-template-columns: minmax(200px, 260px) 1fr minmax(220px, 280px);
    gap: 1.5rem;
    align-items: start;
}
.document-preview nav.toc-tree ul {
    list-style: none;
    padding-left: 0.75rem;
}
.document-preview nav.toc-tree li {
    margin-bottom: 0.25rem;
}
.document-preview nav.toc-tree a {
    color: #11567f;
    text-decoration: none;
}
.document-preview nav.toc-tree a:hover,
.document-preview nav.toc-tree a:focus {
    text-decoration: underline;
}
.document-preview .content-column {
    max-height: 720px;
    overflow-y: auto;
    padding-right: 0.5rem;
}
.document-preview .provision-section {
    padding: 0.75rem 1rem;
    margin-bottom: 1rem;
    border: 1px solid #d9d9d9;
    border-radius: 0.5rem;
    background-color: #fff;
}
.document-preview .provision-section h4 {
    margin-top: 0;
    margin-bottom: 0.25rem;
}
.document-preview .provision-meta {
    font-size: 0.85rem;
    color: #555;
    margin-bottom: 0.75rem;
}
.document-preview .provision-meta span {
    background-color: #f2f6fa;
    padding: 0.1rem 0.35rem;
    border-radius: 999px;
}
.document-preview .atom-badges {
    margin-top: 0.75rem;
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
    align-items: center;
}
.document-preview .atom-badge {
    display: inline-flex;
    align-items: center;
    padding: 0.2rem 0.55rem;
    border-radius: 999px;
    background-color: #ffe6c7;
    color: #8a4f0f;
    font-size: 0.85rem;
    cursor: pointer;
    border: 1px solid rgba(138, 79, 15, 0.2);
}
.document-preview .atom-badge:focus {
    outline: 2px solid #ff9d2e;
    outline-offset: 2px;
}
.document-preview .atom-badge:hover {
    background-color: #ffd59a;
}
.document-preview .detail-column {
    border: 1px solid #d9d9d9;
    border-radius: 0.5rem;
    padding: 0.75rem 1rem;
    background: #fafafa;
    max-height: 720px;
    overflow-y: auto;
}
.document-preview .detail-column pre {
    background: #fff;
    border: 1px solid #ececec;
    border-radius: 0.5rem;
    padding: 0.5rem 0.75rem;
    white-space: pre-wrap;
    word-break: break-word;
}
.document-preview .toc-empty,
.document-preview .no-provisions {
    font-style: italic;
    color: #555;
}
@media (max-width: 1024px) {
    .document-preview .document-columns {
        grid-template-columns: 1fr;
    }
    .document-preview .content-column,
    .document-preview .detail-column {
        max-height: none;
    }
}
</style>
"""

    script = """
<script>
(function() {
    const badges = Array.from(document.querySelectorAll('.atom-badge'));
    const detailColumn = document.getElementById('atom-detail-panel');
    if (!detailColumn) {
        return;
    }
    function renderDetail(label, detailText) {
        let parsed;
        try {
            parsed = JSON.parse(detailText);
        } catch (error) {
            parsed = detailText;
        }
        detailColumn.innerHTML = '';
        const title = document.createElement('h3');
        title.textContent = label || 'Atom details';
        detailColumn.appendChild(title);
        if (typeof parsed === 'string') {
            const paragraph = document.createElement('p');
            paragraph.textContent = parsed;
            detailColumn.appendChild(paragraph);
            return;
        }
        const pre = document.createElement('pre');
        pre.textContent = JSON.stringify(parsed, null, 2);
        detailColumn.appendChild(pre);
    }
    if (badges.length) {
        renderDetail(
            badges[0].getAttribute('data-label'),
            badges[0].getAttribute('data-detail')
        );
    }
    badges.forEach(function(badge) {
        badge.addEventListener('click', function(event) {
            event.preventDefault();
            renderDetail(badge.getAttribute('data-label'), badge.getAttribute('data-detail'));
        });
        badge.addEventListener('keypress', function(event) {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                renderDetail(badge.getAttribute('data-label'), badge.getAttribute('data-detail'));
            }
        });
    });
})();
</script>
"""

    return (
        f"{stylesheet}"
        "<div class='document-preview'>"
        "<div class='document-columns'>"
        "<div class='toc-column'>"
        "<h3>Table of contents</h3>"
        f"{toc_html}"
        "</div>"
        "<div class='content-column'>"
        f"{sections_html}"
        "</div>"
        "<div class='detail-column' id='atom-detail-panel'>"
        "<h3>Atom details</h3>"
        "<p>Select an atom badge to inspect the structured data.</p>"
        "</div>"
        "</div>"
        "</div>"
        f"{script}"
    )


def render_document_preview(document: Document) -> None:
    """Render a cleaned, hyperlinked preview for ``document``."""

    html_content = build_document_preview_html(document)
    components.html(html_content, height=900, scrolling=True)


def _render_table(records: Iterable[Dict[str, Any]], *, key: str) -> None:
    rows = list(records)
    if not rows:
        st.info("No data available for the current selection.")
        return
    if pd is not None:
        frame = pd.DataFrame(rows)
        st.dataframe(frame, use_container_width=True)
    else:  # pragma: no cover - pandas optional
        st.write(rows)
    _download_json(f"Download {key}", rows, f"{key}.json")


def _render_dot(dot: Optional[str], *, key: str) -> None:
    if not dot:
        return
    try:
        st.graphviz_chart(dot)
    except Exception as exc:  # pragma: no cover - graphviz optional
        st.warning(
            f"Graphviz rendering is unavailable ({exc}). Download the DOT file instead."
        )
    st.download_button(
        f"Download {key} DOT",
        dot,
        file_name=f"{key}.dot",
        mime="text/vnd.graphviz",
    )


def _seed_sample_graph() -> None:
    """Populate the FastAPI routes graph with demonstration data."""

    if ROUTES_GRAPH.nodes:
        return

    for identifier, meta in SAMPLE_GRAPH_CASES.items():
        ROUTES_GRAPH.add_node(
            GraphNode(
                type=NodeType.CASE,
                identifier=identifier,
                metadata={"title": meta["title"]},
                cultural_flags=meta.get("cultural_flags"),
                consent_required=meta.get("consent_required", False),
            )
        )

    for source, target, relation, weight in SAMPLE_GRAPH_EDGES:
        metadata = {
            "relation": relation,
            "court": SAMPLE_CASE_TREATMENT_METADATA.get(relation, {}).get(
                "court", "HCA"
            ),
        }
        edge = GraphEdge(
            type=EdgeType.CITES,
            source=source,
            target=target,
            metadata=metadata,
            weight=weight,
        )
        # Duplicate edges raise a ValueError; guard with try/except for idempotence.
        try:
            ROUTES_GRAPH.add_edge(edge)
        except ValueError:
            continue


# ---------------------------------------------------------------------------
# Streamlit page configuration
# ---------------------------------------------------------------------------

st.set_page_config(page_title="SensibLaw Console", layout="wide")
st.title("SensibLaw Operations Console")
st.caption(
    "Interact with SensibLaw services for document processing, concept mapping,"
    " knowledge graph exploration, and more."
)

# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


def render_documents_tab() -> None:
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
            with st.expander("Document metadata and rules", expanded=False):
                st.json(doc_payload)
            _download_json("Download document JSON", doc_payload, "document.json")

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


# ---------------------------------------------------------------------------
# Text & Concepts
# ---------------------------------------------------------------------------


def render_text_concepts_tab() -> None:
    st.subheader("Text & Concepts")
    st.write(
        "Normalise text, surface concept matches, extract rules, and inspect ontology tagging outputs."
    )

    sample_story_path = ROOT / "examples" / "distinguish_glj" / "story.txt"
    sample_text = (
        sample_story_path.read_text(encoding="utf-8")
        if sample_story_path.exists()
        else ""
    )
    default_text = st.session_state.get("concept_input", sample_text)
    text = st.text_area("Input text", value=default_text, height=240)
    st.session_state["concept_input"] = text
    include_dot = st.checkbox("Include DOT exports", value=True)

    if st.button("Analyse text"):
        if not text.strip():
            st.error("Enter some text to analyse.")
            return
        with st.spinner("Running pipeline components"):
            normalised = normalise(text)
            concepts = match_concepts(normalised)
            cloud = build_cloud(concepts)
            advanced_notice: Optional[str] = None
            advanced: Dict[str, Any] = {}
            if ROUTES_GRAPH.nodes and concepts:
                hits: List[Tuple[str, Dict[str, Any]]] = [
                    (concept_id, {"keyword_exact": True}) for concept_id in concepts
                ]
                try:
                    advanced = advanced_cloud(hits, ROUTES_GRAPH)
                except Exception as exc:  # pragma: no cover - defensive UI feedback
                    advanced_notice = f"Unable to build advanced concept cloud: {exc}"
            elif not ROUTES_GRAPH.nodes:
                advanced_notice = "Load the knowledge graph data to enable advanced concept visualisations."
            rules = [r.__dict__ for r in extract_rules(text)]
            provision_payload = api_provision(text, dot=include_dot)
            concept_payload = api_subgraph(text, dot=include_dot)
            rule_payload = api_treatment(text, dot=include_dot)

        st.markdown("#### Normalised text")
        st.code(normalised)
        st.markdown("#### Concept matches")
        st.write(concepts)
        st.markdown("#### Concept cloud")
        if cloud:
            display = (
                pd.DataFrame(
                    {"concept": list(cloud.keys()), "count": list(cloud.values())}
                )
                if pd is not None
                else None
            )
            if display is not None:
                display = display.sort_values("count", ascending=False).set_index(
                    "concept"
                )
                st.bar_chart(display)
                st.dataframe(display, use_container_width=True)
            else:  # pragma: no cover - pandas optional
                st.write(cloud)
        else:
            st.info("No concepts matched the provided text.")
        _download_json("Download concept cloud", cloud, "concept_cloud.json")

        if include_dot:
            _render_dot(concept_payload.get("dot"), key="concept_cloud")

        st.markdown("#### Advanced cloud (concepts.cloud)")
        if advanced:
            st.write(advanced)
        elif advanced_notice:
            st.info(advanced_notice)
        else:
            st.info(
                "No advanced concept relationships available for the supplied text."
            )

        st.markdown("#### Extracted rules")
        _render_table(rules, key="rules")
        if include_dot:
            _render_dot(rule_payload.get("dot"), key="rules")

        st.markdown("#### Provision tagging")
        provision = provision_payload.get("provision", {})
        st.json(provision)
        if include_dot:
            _render_dot(provision_payload.get("dot"), key="provision")


# ---------------------------------------------------------------------------
# Knowledge Graph
# ---------------------------------------------------------------------------


def render_knowledge_graph_tab() -> None:
    st.subheader("Knowledge Graph")
    st.write(
        "Generate subgraphs, execute legal tests, inspect case treatments, and fetch provision atoms."
    )

    if st.button(
        "Load sample graph data", help="Populate the in-memory graph with demo cases"
    ):
        _seed_sample_graph()
        st.success("Sample graph seeded.")

    if not ROUTES_GRAPH.nodes:
        st.info(
            "The in-memory graph is empty. Load the sample dataset above or ingest"
            " your own nodes before running queries."
        )

    st.markdown("### Generate subgraph")
    with st.form("subgraph_form"):
        if ROUTES_GRAPH.nodes:
            seed_default = next(iter(ROUTES_GRAPH.nodes.keys()))
        else:
            seed_default = "Case#Mabo1992"
        seed = st.text_input("Seed node", value=seed_default)
        hops = st.slider("Maximum hops", min_value=1, max_value=5, value=2)
        consent = st.checkbox("Include consent gated nodes", value=False)
        submit = st.form_submit_button("Generate")

    if submit:
        try:
            with st.spinner("Generating subgraph"):
                payload = generate_subgraph(seed, hops, consent=consent)
        except HTTPException as exc:
            st.error(f"{exc.detail} (HTTP {exc.status_code})")
        else:
            st.success("Subgraph generated.")
            st.json(payload)
            _download_json("Download subgraph", payload, "subgraph.json")

    st.markdown("### Execute legal tests")
    template_ids = list(TEMPLATE_REGISTRY.keys())
    with st.form("tests_form"):
        selected_ids = st.multiselect(
            "Test templates", template_ids, default=template_ids[:1]
        )
        default_story = json.dumps(
            {"facts": {fid: True for fid in ("delay",)}}, indent=2
        )
        story_json = st.text_area(
            "Story facts JSON",
            value=st.session_state.get("story_json", default_story),
            height=160,
        )
        st.session_state["story_json"] = story_json
        tests_submit = st.form_submit_button("Run tests")

    if tests_submit:
        try:
            story_payload = json.loads(story_json or "{}")
        except json.JSONDecodeError as exc:
            st.error(f"Invalid JSON: {exc}")
        else:
            facts = story_payload.get("facts", story_payload)
            with st.spinner("Evaluating templates"):
                try:
                    result = execute_tests(selected_ids, facts)
                except HTTPException as exc:
                    st.error(f"{exc.detail} (HTTP {exc.status_code})")
                else:
                    st.json(result)
                    _download_json("Download test results", result, "tests.json")

    st.markdown("### Case treatment summary")
    with st.form("treatment_form"):
        case_id = st.text_input("Case identifier", value="Case#Mabo1992")
        treatment_submit = st.form_submit_button("Fetch treatment")

    if treatment_submit:
        try:
            with st.spinner("Fetching treatment"):
                data = fetch_case_treatment(case_id)
        except HTTPException as exc:
            st.error(f"{exc.detail} (HTTP {exc.status_code})")
        else:
            st.json(data)
            _render_table(data.get("treatments", []), key="treatments")

    st.markdown("### Provision atoms")
    with st.form("provision_form"):
        provision_id = st.text_input(
            "Provision identifier",
            value="Provision#NTA:s223",
        )
        provision_submit = st.form_submit_button("Fetch provision atoms")

    if provision_submit:
        try:
            with st.spinner("Retrieving provision atoms"):
                provision = fetch_provision_atoms(provision_id)
        except HTTPException as exc:
            st.error(f"{exc.detail} (HTTP {exc.status_code})")
        else:
            st.json(provision)
            _download_json(
                "Download provision atoms", provision, "provision_atoms.json"
            )


# ---------------------------------------------------------------------------
# Case Comparison
# ---------------------------------------------------------------------------


def render_case_comparison_tab() -> None:
    st.subheader("Case Comparison")
    st.write(
        "Load a base silhouette and compare story fact tags to highlight overlaps and gaps."
    )

    case_label = st.selectbox("Base case", list(SAMPLE_CASES.keys()))
    citation = SAMPLE_CASES[case_label]

    sample_story_json = json.dumps(SAMPLE_STORY_FACTS, indent=2)
    uploaded_story = st.file_uploader(
        "Upload story JSON (expects a {'facts': {...}} mapping)",
        type=["json"],
        key="story_upload",
    )
    if uploaded_story is not None:
        story_text = uploaded_story.read().decode("utf-8")
    else:
        story_text = st.text_area(
            "Story facts JSON",
            value=st.session_state.get("comparison_story", sample_story_json),
            height=200,
        )
    st.session_state["comparison_story"] = story_text

    if st.button("Compare story to case"):
        try:
            payload = json.loads(story_text or "{}")
        except json.JSONDecodeError as exc:
            st.error(f"Invalid JSON: {exc}")
            return
        story_tags = payload.get("facts", payload)
        with st.spinner("Loading silhouette and computing comparison"):
            try:
                silhouette = load_case_silhouette(citation)
            except Exception as exc:  # pragma: no cover - loader raises KeyError
                st.error(str(exc))
                return
            comparison = compare_story_to_case(story_tags, silhouette)
        st.success("Comparison complete.")
        st.json(comparison)
        _download_json("Download comparison", comparison, "case_comparison.json")

        overlaps = [
            {
                "id": item.get("id"),
                "paragraph": item.get("candidate", {}).get("paragraph"),
                "anchor": item.get("candidate", {}).get("anchor"),
            }
            for item in comparison.get("overlaps", [])
        ]
        missing = [
            {
                "id": item.get("id"),
                "anchor": item.get("candidate", {}).get("anchor"),
            }
            for item in comparison.get("missing", [])
        ]
        st.markdown("#### Overlaps")
        _render_table(overlaps, key="overlaps")
        st.markdown("#### Missing")
        _render_table(missing, key="missing")


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def render_utilities_tab() -> None:
    st.subheader("Utilities")
    st.write(
        "Quick access to glossary lookups, frame compilation, receipts, similarity fingerprints, FRL ingestion, rule checks, and harm scores."
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


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------


def main() -> None:
    documents_tab, text_tab, graph_tab, comparison_tab, utilities_tab = st.tabs(
        [
            "Documents",
            "Text & Concepts",
            "Knowledge Graph",
            "Case Comparison",
            "Utilities",
        ]
    )

    with documents_tab:
        render_documents_tab()
    with text_tab:
        render_text_concepts_tab()
    with graph_tab:
        render_knowledge_graph_tab()
    with comparison_tab:
        render_case_comparison_tab()
    with utilities_tab:
        render_utilities_tab()


if __name__ == "__main__":  # pragma: no cover - streamlit executes main
    main()
