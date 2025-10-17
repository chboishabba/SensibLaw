"""Shared helpers for the SensibLaw Streamlit console."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import streamlit as st

from . import REPO_ROOT

try:  # Optional dependency for tabular display
    import pandas as pd
except Exception:  # pragma: no cover - pandas is optional at runtime
    pd = None  # type: ignore[assignment]

try:  # Optional dependency for graph rendering
    from graphviz import Digraph
except Exception:  # pragma: no cover - graphviz is optional at runtime
    Digraph = None  # type: ignore[assignment]

ROOT = REPO_ROOT


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _write_bytes(path: Path, data: bytes) -> Path:
    _ensure_parent(path)
    path.write_bytes(data)
    return path


def _json_default(value: Any) -> Any:
    """Provide JSON-serialisation fallbacks for complex objects."""

    if isinstance(value, Enum):
        return value.value
    if isinstance(value, date):
        return value.isoformat()
    if is_dataclass(value):
        return asdict(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serialisable")


def _download_json(
    label: str, payload: Any, filename: str, *, key: Optional[str] = None
) -> None:
    st.download_button(
        label,
        json.dumps(payload, indent=2, ensure_ascii=False, default=_json_default),
        file_name=filename,
        mime="application/json",
        key=key,
    )


def _render_table(records: Iterable[Dict[str, Any]], *, key: str) -> None:
    rows = list(records)
    if not rows:
        st.info("No data available for the current selection.")
        return
    if pd is not None:
        frame = pd.DataFrame(rows)
        st.dataframe(frame, use_container_width=True)
    else:  # pragma: no cover - pandas optional
        st.write(rows)
    _download_json(f"Download {key}", rows, f"{key}.json")


def _render_dot(dot: Optional[str], *, key: str) -> None:
    if not dot:
        return
    try:
        st.graphviz_chart(dot)
    except Exception as exc:  # pragma: no cover - graphviz optional
        st.warning(
            f"Graphviz rendering is unavailable ({exc}). Download the DOT file instead."
        )
    st.download_button(
        f"Download {key} DOT",
        dot,
        file_name=f"{key}.dot",
        mime="text/vnd.graphviz",
    )


def _build_knowledge_graph_dot(payload: Dict[str, Any]) -> Optional[str]:
    """Construct a Graphviz representation of a knowledge graph payload."""

    if Digraph is None:
        return None

    graph = Digraph("knowledge_graph", format="svg")
    graph.attr("graph", rankdir="LR", bgcolor="white")
    graph.attr("node", shape="ellipse", style="filled", fillcolor="white")

    node_type_styles = {
        "case": {"shape": "box", "fillcolor": "#E8F1FF"},
        "provision": {"shape": "oval", "fillcolor": "#F4F0FF"},
        "concept": {"shape": "hexagon", "fillcolor": "#FFF4E5"},
        "person": {"shape": "diamond", "fillcolor": "#EAF9F0"},
        "document": {"shape": "note", "fillcolor": "#FFFBEA"},
    }

    nodes = payload.get("nodes", []) or []
    edges = payload.get("edges", []) or []

    def _enum_value(value: Any) -> str:
        if hasattr(value, "value"):
            return str(value.value)
        if isinstance(value, str):
            return value.split(".")[-1].lower()
        return str(value)

    for node in nodes:
        identifier = node.get("identifier")
        if not identifier:
            continue

        node_type = _enum_value(node.get("type", ""))
        metadata = node.get("metadata") or {}
        title = metadata.get("title") or metadata.get("name") or identifier
        subtitle_parts = []
        for key in ("court", "year", "citation"):
            value = metadata.get(key)
            if value:
                subtitle_parts.append(str(value))
        if node.get("date") and not metadata.get("year"):
            subtitle_parts.append(str(node["date"]))
        if metadata.get("role"):
            subtitle_parts.append(str(metadata["role"]))

        label = title
        if subtitle_parts:
            label = f"{title}\n" + " | ".join(subtitle_parts)

        node_attrs = node_type_styles.get(node_type, {})
        if node.get("consent_required"):
            node_attrs = {
                **node_attrs,
                "fillcolor": "#FFE8E5",
                "style": "filled,dashed",
            }

        if metadata.get("cultural_flags") or node.get("cultural_flags"):
            node_attrs = {**node_attrs, "color": "#C94C4C", "penwidth": "2"}

        graph.node(identifier, label=label, **node_attrs)

    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")
        if not source or not target:
            continue

        edge_type = _enum_value(edge.get("type", ""))
        label = edge_type.replace("_", " ").title() if edge_type else ""
        weight = edge.get("weight")
        if isinstance(weight, (int, float)) and weight != 1:
            label = f"{label} ({weight:g})" if label else f"{weight:g}"

        color = "#1D4ED8"
        if edge_type in {"distinguishes", "rejects", "overrules"}:
            color = "#B91C1C"
        elif edge_type in {"follows", "applies", "considers"}:
            color = "#047857"

        edge_attrs: Dict[str, Any] = {"color": color}
        if label:
            edge_attrs["label"] = label

        graph.edge(source, target, **edge_attrs)

    return graph.source


__all__ = [
    "ROOT",
    "pd",
    "_ensure_parent",
    "_write_bytes",
    "_download_json",
    "_render_table",
    "_render_dot",
    "_build_knowledge_graph_dot",
]
