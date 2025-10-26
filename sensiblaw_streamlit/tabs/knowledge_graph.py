"""Knowledge Graph tab for the SensibLaw Streamlit console."""

from __future__ import annotations

import json

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


__all__ = ["render"]
