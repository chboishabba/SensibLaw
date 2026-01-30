from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from src.review_collection import (
    compare_bundles,
    load_collection,
    manifest as build_manifest,
)


def _load_bundle(base: Path, rel_path: str) -> dict:
    bpath = (base / rel_path).resolve()
    return json.loads(bpath.read_text(encoding="utf-8"))


def render() -> None:
    st.subheader("Review Collections (read-only)")
    default_collection = "examples/review_collection_minimal.json"
    collection_path = st.text_input("Collection path", value=default_collection)
    collection_file = Path(collection_path)
    if not collection_file.exists():
        st.warning("Collection file not found.")
        return

    try:
        col = load_collection(collection_file)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Failed to load collection: {exc}")
        return

    st.markdown("**Manifest**")
    manifest = build_manifest(collection_file)
    st.json(manifest, expanded=False)

    if len(col["bundles"]) < 2:
        st.info("Add more bundles to compare.")
        return

    labels = [item.get("label", item["path"]) for item in col["bundles"]]
    left_idx = st.selectbox("Left bundle", range(len(labels)), format_func=lambda i: labels[i], index=0)
    right_idx = st.selectbox("Right bundle", range(len(labels)), format_func=lambda i: labels[i], index=1)
    if left_idx == right_idx:
        st.info("Select two different bundles to compare.")
        return

    base_dir = collection_file.parent
    left_item = col["bundles"][left_idx]
    right_item = col["bundles"][right_idx]
    left = _load_bundle(base_dir, left_item["path"])
    right = _load_bundle(base_dir, right_item["path"])
    diff = compare_bundles(left, right)

    st.markdown("**Structural diff (hash-based, no semantics)**")
    st.json(diff, expanded=False)


__all__ = ["render"]
