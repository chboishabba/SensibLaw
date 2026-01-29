import streamlit as st


def render_obligations(payload: dict):
    st.subheader("Obligations (read-only)")
    obligations = payload.get("obligations") or payload.get("obligation") or {}
    if not obligations:
        st.info("No obligations payload found in JSON.")
        return
    st.json(obligations, expanded=False)
