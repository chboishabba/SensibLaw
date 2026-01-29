import streamlit as st


def render_activation(payload: dict):
    st.subheader("Activation (descriptive, non-reasoning)")
    activation = payload.get("activation") or payload.get("obligation_activation") or {}
    if not activation:
        st.info("No activation block present.")
        return
    st.json(activation, expanded=False)
