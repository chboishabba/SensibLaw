"""Shared helpers for the SensibLaw Streamlit console."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, is_dataclass
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import streamlit as st

from . import REPO_ROOT
from src.graph.principle_graph import build_principle_graph

try:  # Optional dependency for tabular display
    import pandas as pd
except Exception:  # pragma: no cover - pandas is optional at runtime
    pd = None  # type: ignore[assignment]

try:  # Optional dependency for graph rendering
    from graphviz import Digraph
except Exception:  # pragma: no cover - graphviz is optional at runtime
    Digraph = None  # type: ignore[assignment]

ROOT = REPO_ROOT
UI_FIXTURE_DIR = Path(os.getenv("SENSIBLAW_UI_FIXTURE_DIR", ROOT / "tests" / "fixtures" / "ui"))
FORBIDDEN_TERMS = {
    "compliance",
    "breach",
    "prevails",
    "valid",
    "invalid",
    "stronger",
    "weaker",
    "satisfies",
    "violates",
    "binding",
    "override",
}


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


def _load_fixture(param_name: str, env_var: str) -> Optional[Dict[str, Any]]:
    """Load a UI fixture if specified via query param or env var.

    - Query param takes priority (e.g. ?graph_fixture=knowledge_graph_minimal.json)
    - Falls back to env var pointing to an absolute path or filename inside UI_FIXTURE_DIR
    """

    try:
        params = st.query_params  # modern Streamlit API
    except Exception:  # pragma: no cover - fallback for older Streamlit
        try:
            params = st.experimental_get_query_params()
        except Exception:
            params = {}

    candidate = None
    if isinstance(params, dict):
        value = params.get(param_name)
        if isinstance(value, list):
            candidate = value[0] if value else None
        elif isinstance(value, str):
            candidate = value
    candidate = candidate or os.getenv(env_var)
    if not candidate:
        return None

    path = Path(candidate)
    if not path.is_absolute():
        path = UI_FIXTURE_DIR / candidate
    if not path.exists():
        st.error(f"Fixture not found: {path}")
        return None

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        st.error(f"Failed to load fixture {path}: {exc}")
        return None


def _warn_forbidden(text: str) -> None:
    """Emit a UI warning if forbidden semantic terms are present."""

    lowered = text.lower()
    hits = [term for term in FORBIDDEN_TERMS if term in lowered]
    if hits:
        st.error(f"Forbidden semantic terms detected: {', '.join(sorted(set(hits)))}")


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


def _build_principle_graph_dot(provision: Dict[str, Any]) -> Optional[str]:
    """Render a provision's principles, issues, and authorities."""

    if Digraph is None:
        return None

    graph_payload = build_principle_graph(provision)
    graph = Digraph("principle_graph", format="svg")
    graph.attr("graph", rankdir="LR", bgcolor="white")
    graph.attr("node", style="filled", fontname="Helvetica")

    kind_styles: Dict[str, Dict[str, Any]] = {
        "provision": {"shape": "folder", "fillcolor": "#EEF2FF"},
        "principle": {"shape": "box", "fillcolor": "#DBEAFE"},
        "issue": {"shape": "ellipse", "fillcolor": "#FEF3C7"},
        "fact": {"shape": "ellipse", "fillcolor": "#E0F2FE"},
        "policy": {"shape": "hexagon", "fillcolor": "#FDE68A"},
        "case": {"shape": "box", "fillcolor": "#E8F1FF"},
        "statute": {"shape": "oval", "fillcolor": "#F4F0FF"},
        "authority": {"shape": "note", "fillcolor": "#FFFBEA"},
    }
    status_colors = {
        "proven": "#DCFCE7",
        "pending": "#FEF3C7",
        "contested": "#FEE2E2",
        "rejected": "#FEE2E2",
    }

    def _format_status(meta: Dict[str, Any]) -> Optional[str]:
        status = meta.get("status")
        if not status:
            return None
        status_text = str(status).title()
        confidence = meta.get("confidence")
        if isinstance(confidence, (int, float)):
            if 0 <= confidence <= 1:
                status_text += f" ({confidence:.0%})"
            else:
                status_text += f" ({confidence})"
        evidence = meta.get("evidence_count")
        if isinstance(evidence, (int, float)):
            suffix = "s" if evidence != 1 else ""
            status_text += f" — {int(evidence)} source{suffix}"
        return status_text

    for node in graph_payload.get("nodes", []):
        node_id = str(node.get("id"))
        if not node_id:
            continue
        label = str(node.get("label") or node_id)
        metadata = node.get("metadata") or {}

        lines = [label]
        summary = metadata.get("summary")
        if summary and summary not in lines:
            lines.append(str(summary))
        tags = metadata.get("tags")
        if tags:
            tag_line = ", ".join(str(tag) for tag in tags)
            if tag_line:
                lines.append(tag_line)
        status_line = _format_status(metadata)
        if status_line:
            lines.append(status_line)
        notes = metadata.get("notes")
        if notes:
            lines.append(str(notes))

        kind = str(node.get("kind") or "").lower()
        node_attrs = dict(
            kind_styles.get(kind, {"shape": "ellipse", "fillcolor": "#FFFFFF"})
        )
        status = metadata.get("status")
        if isinstance(status, str):
            node_attrs["fillcolor"] = status_colors.get(
                status.lower(), node_attrs.get("fillcolor", "#FFFFFF")
            )

        graph.node(node_id, label="\n".join(lines), **node_attrs)

    edge_colors = {
        "principle": "#6366F1",
        "issue": "#7C3AED",
        "fact": "#2563EB",
        "policy": "#8B5CF6",
        "case": "#0EA5E9",
        "statute": "#0284C7",
        "authority": "#0EA5E9",
    }

    for edge in graph_payload.get("edges", []):
        source = edge.get("source")
        target = edge.get("target")
        if not source or not target:
            continue
        label = edge.get("label")
        metadata = edge.get("metadata") or {}
        edge_kind = str(edge.get("kind") or label or "").lower()

        text_label = str(label) if label else ""
        if text_label:
            text_label = text_label.replace("_", " ")
        pinpoint = metadata.get("pinpoint")
        if pinpoint:
            pinpoint_text = str(pinpoint)
            text_label = (
                f"{text_label} ({pinpoint_text})" if text_label else pinpoint_text
            )

        edge_attrs: Dict[str, Any] = {
            "color": edge_colors.get(edge_kind, "#4B5563"),
        }
        if text_label:
            edge_attrs["label"] = text_label

        graph.edge(str(source), str(target), **edge_attrs)

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
    "_build_principle_graph_dot",
]
