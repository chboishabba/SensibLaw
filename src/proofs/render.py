"""Render proof graphs with optional harm overlay."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable
import subprocess

from graph.proof_tree import Edge, Node, to_dot

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - dependency may not be present
    yaml = None  # type: ignore


def load_harm_index(path: Path) -> Dict[str, float]:
    """Load harm weights from a YAML file.

    Parameters
    ----------
    path:
        Location of the YAML file mapping entities to harm weights.
    """

    text = path.read_text()
    if yaml is not None:
        data = yaml.safe_load(text)
        return {entity: float(info["weight"]) for entity, info in data.items()}
    # Fallback minimal parser supporting the file structure used in this repo
    index: Dict[str, float] = {}
    current: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if not line.startswith("-") and line.endswith(":"):
            current = line[:-1]
        elif line.startswith("weight:") and current:
            index[current] = float(line.split(":", 1)[1].strip())
            current = None
    return index


def _weight_to_color(weight: float) -> str:
    """Map a weight in [0,1] to a hex color from green to red."""

    weight = max(0.0, min(1.0, weight))
    r = int(weight * 255)
    g = int((1 - weight) * 255)
    return f"#{r:02x}{g:02x}00"


def to_dot_with_harm(
    nodes: Dict[str, Node],
    edges: Iterable[Edge],
    harm_index: Dict[str, float],
) -> str:
    """Export nodes and edges to DOT format with harm-based colouring."""

    lines = ["digraph G {"]
    for node in nodes.values():
        label = str(node.metadata.get("label", node.id))
        entity = node.metadata.get("entity")
        attrs = [f'label="{label}"']
        if entity:
            weight = harm_index.get(entity, 0.0)
            color = _weight_to_color(weight)
            attrs.extend(["style=filled", f'fillcolor="{color}"'])
        lines.append(f'  "{node.id}" [{", ".join(attrs)}];')
    for edge in edges:
        label = str(edge.metadata.get("label", edge.type))
        attrs = [f'label="{label}"']
        receipt = edge.metadata.get("receipt")
        if receipt:
            attrs.append(f'receipt="{receipt}"')
        if edge.weight is not None:
            attrs.append(f'weight="{edge.weight}"')
        tooltip = receipt or label or "why is this here?"
        attrs.append(f'tooltip="{tooltip}"')
        lines.append(
            f'  "{edge.source}" -> "{edge.target}" [{", ".join(attrs)}];'
        )
    lines.append("}")
    return "\n".join(lines)


def dot_to_svg(dot: str) -> str:
    """Convert DOT text to an SVG string using Graphviz."""

    try:
        result = subprocess.run(
            ["dot", "-Tsvg"],
            input=dot.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("Graphviz 'dot' executable not found") from exc
    return result.stdout.decode("utf-8")


def to_svg(nodes: Dict[str, Node], edges: Iterable[Edge]) -> str:
    """Render nodes and edges directly to an SVG string."""

    dot = to_dot(nodes, edges)
    return dot_to_svg(dot)
