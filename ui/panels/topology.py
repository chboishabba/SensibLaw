import streamlit as st


def render_topology(payload: dict):
    st.subheader("Cross-Document Topology")
    topology = payload.get("topology") or payload.get("obligation_crossdoc") or {}
    if not topology:
        st.info("No cross-document topology provided.")
        return
    st.json(topology, expanded=False)
