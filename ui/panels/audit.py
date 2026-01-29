import streamlit as st


def render_audit(payload: dict):
    st.subheader("Audit / Review Metadata")
    notes = payload.get("notes", [])
    disagreements = payload.get("disagreements", [])
    if not notes and not disagreements:
        st.info("No review metadata present.")
        return
    if notes:
        st.markdown("**Reviewer Notes**")
        st.json(notes, expanded=False)
    if disagreements:
        st.markdown("**Disagreement Markers**")
        st.json(disagreements, expanded=False)
