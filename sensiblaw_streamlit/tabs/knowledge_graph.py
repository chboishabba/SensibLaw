"""Knowledge Graph tab for the SensibLaw Streamlit console."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List
from typing import Any, Dict, List, Optional

import streamlit as st

from sensiblaw_streamlit.constants import (
    SAMPLE_CASE_TREATMENT_METADATA,
    SAMPLE_GRAPH_CASES,
    SAMPLE_GRAPH_EDGES,
)
from sensiblaw_streamlit.shared import (
    _build_knowledge_graph_dot,
    _download_json,
    _render_dot,
    _render_table,
)

from src.api.routes import (
    HTTPException,
    _graph as ROUTES_GRAPH,
    ensure_sample_treatment_graph,
    execute_tests,
    fetch_case_treatment,
    fetch_provision_atoms,
    generate_subgraph,
)
from src.graph.models import EdgeType, GraphEdge, GraphNode, NodeType
from src.tests.templates import TEMPLATE_REGISTRY


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
        try:
            ROUTES_GRAPH.add_edge(edge)
        except ValueError:
            continue


def _escape_markdown(text: str) -> str:
    """Escape Markdown control characters for safe rendering."""

    if not isinstance(text, str):
        return str(text)
    return re.sub(r"([\\`*_{}\[\]()#+\-!])", r"\\\\\1", text)


def _format_proof(proof: Dict[str, Any]) -> str:
    """Build a human friendly summary of the proof payload."""

    if not proof:
        return "status unknown"

    status = _escape_markdown(str(proof.get("status", "unknown"))).capitalize()
    details: List[str] = []

    confidence = proof.get("confidence")
    if isinstance(confidence, (int, float)):
        if 0 <= confidence <= 1:
            details.append(f"confidence {confidence:.0%}")
        else:
            details.append(f"confidence {confidence}")

    evidence_count = proof.get("evidenceCount")
    if isinstance(evidence_count, (int, float)):
        suffix = "s" if evidence_count != 1 else ""
        details.append(f"{int(evidence_count)} evidence source{suffix}")

    if details:
        return f"{status} ({', '.join(details)})"
    return status


def _build_atom_lines(atom: Dict[str, Any], depth: int = 0) -> List[str]:
    """Recursively render provision atoms into a Markdown bullet list."""

    indent = "  " * depth
    label = _escape_markdown(atom.get("label") or atom.get("id") or "Unnamed atom")
    role = atom.get("role")
    role_segment = f"*{_escape_markdown(role)}*" if role else None
    proof_segment = _format_proof(atom.get("proof", {}))

    meta_segments = [segment for segment in (role_segment, proof_segment) if segment]
    headline = f"{indent}- **{label}**"
    if meta_segments:
        headline += " — " + ", ".join(meta_segments)

    lines = [headline]

    notes = atom.get("notes")
    if notes:
        lines.append(f"{indent}  _Notes_: {_escape_markdown(str(notes))}")

    principle = atom.get("principle") or {}
    principle_title = principle.get("title")
    principle_summary = principle.get("summary")
    if principle_title or principle_summary:
        summary_parts = []
        if principle_title:
            summary_parts.append(f"**{_escape_markdown(str(principle_title))}**")
        if principle_summary:
            summary_parts.append(_escape_markdown(str(principle_summary)))
        lines.append(f"{indent}  _Principle_: {' — '.join(summary_parts)}")

    principle_tags = principle.get("tags")
    if principle_tags:
        escaped_tags = ", ".join(_escape_markdown(str(tag)) for tag in principle_tags)
        lines.append(f"{indent}  _Tags_: {escaped_tags}")

    principle_citation = principle.get("citation")
    if principle_citation:
        lines.append(
            f"{indent}  _Citation_: `{_escape_markdown(str(principle_citation))}`"
        )

    for child in atom.get("children", []) or []:
        lines.extend(_build_atom_lines(child, depth + 1))

    return lines


def _render_provision_atoms(provision: Dict[str, Any]) -> None:
    """Render provision atoms in a readable outline with the raw JSON in an expander."""

    title = provision.get("title")
    provision_id = provision.get("provision_id")
    if title:
        st.markdown(f"**{_escape_markdown(str(title))}**")
    if provision_id:
        st.caption(_escape_markdown(str(provision_id)))

    atoms = provision.get("atoms", [])
    if not atoms:
        st.info("No atoms available for this provision.")
        return

    atom_lines: List[str] = []
    for atom in atoms:
        atom_lines.extend(_build_atom_lines(atom))

    st.markdown("\n".join(atom_lines))

    with st.expander("Show raw JSON response", expanded=False):
        st.json(provision)
def _available_case_identifiers() -> List[str]:
    """Return sorted case identifiers currently present in the graph."""

    if not ROUTES_GRAPH.nodes:
        ensure_sample_treatment_graph()

    identifiers = [
        identifier
        for identifier, node in ROUTES_GRAPH.nodes.items()
        if getattr(node, "type", None) in (NodeType.CASE, NodeType.DOCUMENT)
    ]
    identifiers.sort()
    return identifiers


def render() -> None:
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
            dot = _build_knowledge_graph_dot(payload)
            if dot:
                _render_dot(dot, key="knowledge_subgraph")
            else:
                st.info(
                    "Graphviz is not available. Install the optional dependency to see"
                    " the visualisation."
                )
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
    available_case_ids = _available_case_identifiers()

    selected_case_id: Optional[str] = None
    if available_case_ids:
        selected_case_id = st.selectbox(
            "Available cases",
            options=available_case_ids,
            key="kg_case_id_select",
            help="Select from cases loaded into the in-memory graph.",
        )
    else:
        st.info(
            "No cases are available yet. Load the sample graph or ingest data to enable"
            " treatment summaries."
        )

    if "kg_case_id_input" not in st.session_state:
        st.session_state["kg_case_id_input"] = selected_case_id or "Case#Mabo1992"

    previous_selection = st.session_state.get("kg_case_id_select_prev")
    if (
        selected_case_id
        and selected_case_id != previous_selection
        and st.session_state.get("kg_case_id_input") in (None, "", previous_selection)
    ):
        st.session_state["kg_case_id_input"] = selected_case_id
    st.session_state["kg_case_id_select_prev"] = selected_case_id

    case_id = st.text_input(
        "Case identifier",
        key="kg_case_id_input",
        help="Enter the identifier for a case stored in the knowledge graph.",
    )
    treatment_submit = st.button("Fetch treatment", key="kg_fetch_treatment")

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
            _render_provision_atoms(provision)
            _download_json(
                "Download provision atoms", provision, "provision_atoms.json"
            )


__all__ = ["render"]
