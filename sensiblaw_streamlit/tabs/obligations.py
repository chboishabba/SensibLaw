"""Obligations tab (read-only)."""

from __future__ import annotations

import streamlit as st

from sensiblaw_streamlit.shared import _load_fixture, _warn_forbidden, _download_json


def _extract_results(payload: dict) -> list[dict]:
    if not payload:
        return []
    if "results" in payload:
        return list(payload.get("results") or [])
    if "obligations" in payload:
        return list(payload.get("obligations") or [])
    return []


def render() -> None:
    st.subheader("Obligations (read-only)")
    payload = _load_fixture("obligations_fixture", "SENSIBLAW_OBLIGATIONS_FIXTURE")
    if payload is None:
        st.info("No obligations fixture loaded. Provide obligations_fixture=... to enable fixture mode.")
        return

    st.caption("Fixture mode")
    _warn_forbidden(str(payload))

    results = _extract_results(payload)
    if not results:
        st.warning("No obligation results in fixture payload.")
        return

    clause_ids = [item.get("clause_id", f"item-{idx}") for idx, item in enumerate(results)]
    selected = st.selectbox("Select obligation", clause_ids, index=0)
    selected_item = results[clause_ids.index(selected)]

    st.markdown("### Obligation")
    st.json(selected_item, expanded=False)

    st.markdown("### Span inspector")
    span = selected_item.get("span")
    clause_text = selected_item.get("clause_text")
    if span:
        st.write({"span": span})
        if clause_text:
            tokens = clause_text.split()
            start, end = span if len(span) == 2 else (None, None)
            if start is not None and end is not None and start < end:
                highlighted = tokens[:start] + ["**" + " ".join(tokens[start:end]) + "**"] + tokens[end:]
                st.markdown(" ".join(highlighted))
    else:
        st.info("No span attached to this obligation.")

    st.markdown("### Provenance")
    st.json(selected_item.get("provenance", {}), expanded=False)

    st.markdown("### Signal hypotheses")
    st.json(selected_item.get("signal_hypotheses", []), expanded=False)

    st.markdown("### Promotion receipts")
    st.json(selected_item.get("promotion_receipts", []), expanded=False)

    _download_json("Download obligations", payload, "obligations_fixture.json")


__all__ = ["render"]
