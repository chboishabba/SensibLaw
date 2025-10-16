"""Text & Concepts tab for the SensibLaw Streamlit console."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

from src.api.routes import _graph as ROUTES_GRAPH
from src.api.sample_routes import api_provision, api_subgraph, api_treatment
from src.concepts.cloud import build_cloud as advanced_cloud
from src.pipeline import build_cloud, match_concepts, normalise
from src.rules.extractor import extract_rules

from ..constants import REPO_ROOT
from ..shared import _download_json, _render_dot, _render_table, pd


def render() -> None:
    """Render the Text & Concepts tab."""

    st.subheader("Text & Concepts")
    st.write(
        "Normalise text, surface concept matches, extract rules, and inspect ontology tagging outputs."
    )

    sample_story_path = REPO_ROOT / "examples" / "distinguish_glj" / "story.txt"
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
