"""Streamlit application entrypoint for the SensibLaw console."""

from __future__ import annotations

import streamlit as st

from sensiblaw_streamlit.tabs import (
    case_comparison,
    collections,
    documents,
    knowledge_graph,
    text_concepts,
    utilities,
)


def configure_page() -> None:
    st.set_page_config(page_title="SensibLaw Console", layout="wide")
    st.title("SensibLaw Operations Console")
    st.caption(
        "Interact with SensibLaw services for document processing, concept mapping,"
        " knowledge graph exploration, and more."
    )


def main() -> None:
    configure_page()

    documents_tab, text_tab, graph_tab, comparison_tab, collections_tab, utilities_tab = st.tabs(
        [
            "Documents",
            "Text & Concepts",
            "Knowledge Graph",
            "Case Comparison",
            "Collections",
            "Utilities",
        ]
    )

    with documents_tab:
        documents.render()
    with text_tab:
        text_concepts.render()
    with graph_tab:
        knowledge_graph.render()
    with comparison_tab:
        case_comparison.render()
    with collections_tab:
        collections.render()
    with utilities_tab:
        utilities.render()


__all__ = ["main"]
