"""Streamlit application entrypoint for the SensibLaw console."""

from __future__ import annotations

import sys

import streamlit as st

from .constants import SRC_DIR

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from .tabs.case_comparison import render as render_case_comparison_tab
from .tabs.documents import render as render_documents_tab
from .tabs.knowledge_graph import render as render_knowledge_graph_tab
from .tabs.text_concepts import render as render_text_concepts_tab
from .tabs.utilities import render as render_utilities_tab

st.set_page_config(page_title="SensibLaw Console", layout="wide")


def main() -> None:
    """Render the Streamlit application."""

    st.title("SensibLaw Operations Console")
    st.caption(
        "Interact with SensibLaw services for document processing, concept mapping, knowledge graph exploration, and more."
    )

    (
        documents_tab,
        text_tab,
        graph_tab,
        comparison_tab,
        utilities_tab,
    ) = st.tabs(
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


__all__ = ["main"]
