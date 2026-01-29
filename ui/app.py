import json
from pathlib import Path

import streamlit as st

from ui.panels.activation import render_activation
from ui.panels.audit import render_audit
from ui.panels.obligations import render_obligations
from ui.panels.topology import render_topology


def _load_json(path_str: str):
    if not path_str:
        st.info("Provide a path to a payload JSON file.")
        return None
    path = Path(path_str).expanduser()
    if not path.exists():
        st.error(f"File not found: {path}")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        st.error(f"Invalid JSON: {exc}")
        return None


def main():
    st.set_page_config(page_title="SensibLaw Review", layout="wide")
    st.title("SensibLaw Review (Read-Only)")
    st.caption("Human inspection only — no mutation, no reasoning.")
    st.warning("Read-only review. No reasoning or compliance judgments are performed.")

    st.sidebar.header("Load payload")
    use_example = st.sidebar.checkbox("Load example bundle", value=True)
    if use_example:
        payload_path = str(Path(__file__).resolve().parents[1] / "examples" / "review_bundle_minimal.json")
        st.sidebar.write(f"Using example: {payload_path}")
    else:
        payload_path = st.sidebar.text_input("Payload JSON path", "")

    payload = _load_json(payload_path)
    if payload is None:
        return

    tab_obl, tab_act, tab_topo, tab_audit = st.tabs(["Obligations", "Activation", "Topology", "Audit"])
    with tab_obl:
        render_obligations(payload)
    with tab_act:
        render_activation(payload)
    with tab_topo:
        render_topology(payload)
    with tab_audit:
        render_audit(payload)


if __name__ == "__main__":
    main()
