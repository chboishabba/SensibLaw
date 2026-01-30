"""Case Comparison tab for the SensibLaw Streamlit console."""

from __future__ import annotations

import json

import streamlit as st

from sensiblaw_streamlit.constants import SAMPLE_CASES, SAMPLE_STORY_FACTS
from sensiblaw_streamlit.shared import (
    _download_json,
    _load_fixture,
    _render_table,
    _warn_forbidden,
)

from src.distinguish.engine import compare_story_to_case
from src.distinguish.loader import load_case_silhouette


def render() -> None:
    st.subheader("Case Comparison")
    st.write(
        "Load a base silhouette and compare story fact tags to highlight overlaps and gaps."
    )

    fixture = _load_fixture("case_fixture", "SENSIBLAW_CASE_FIXTURE")
    if fixture:
        st.caption("Fixture mode (structural diff only)")
        diff = fixture.get("diff", {})
        st.markdown("#### Added")
        st.write(diff.get("added", []))
        st.markdown("#### Removed")
        st.write(diff.get("removed", []))
        st.markdown("#### Unchanged")
        st.write(diff.get("unchanged", []))
        _warn_forbidden(json.dumps(fixture))
        return

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


__all__ = ["render"]
