from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from src.ingestion.media_adapter import CanonicalText, SegmentKind
from src.ingestion.structure_graph import SegmentGraph


@dataclass(frozen=True)
class StructureMetrics:
    input_signal: dict[str, object]
    output_signal: dict[str, object]
    fidelity: float
    gain: float
    graph_structuredness: float

    def to_dict(self) -> dict[str, object]:
        return {
            "input_signal": dict(self.input_signal),
            "output_signal": dict(self.output_signal),
            "fidelity": self.fidelity,
            "gain": self.gain,
            "graph_structuredness": self.graph_structuredness,
        }


def _ratio(count: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(count / total, 6)


def compute_input_structure_signal(canonical_text: CanonicalText) -> dict[str, object]:
    segments = list(canonical_text.segments)
    segment_count = len(segments)
    kind_counts = Counter(segment.segment_kind for segment in segments)
    structural_segment_count = sum(
        count
        for kind, count in kind_counts.items()
        if kind
        and kind != SegmentKind.PARAGRAPH.value
        and kind != SegmentKind.DIVIDER.value
    )
    return {
        "segment_count": segment_count,
        "segment_kind_counts": dict(sorted(kind_counts.items())),
        "structural_segment_count": structural_segment_count,
        "structural_density": _ratio(structural_segment_count, segment_count),
    }


def compute_output_structure_signal(segment_graph: SegmentGraph) -> dict[str, object]:
    nodes = list(segment_graph.nodes)
    edges = list(segment_graph.edges)
    role_counts = Counter(node.role or "unknown" for node in nodes)
    edge_counts = Counter(edge.edge_kind for edge in edges)
    segment_node_count = sum(1 for node in nodes if node.role != "root")
    structural_node_count = sum(
        count for role, count in role_counts.items() if role not in {"root", "body", "unknown"}
    )
    return {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "segment_node_count": segment_node_count,
        "role_counts": dict(sorted(role_counts.items())),
        "edge_kind_counts": dict(sorted(edge_counts.items())),
        "structural_node_count": structural_node_count,
        "structural_density": _ratio(structural_node_count, segment_node_count),
    }


def compute_structure_metrics(
    canonical_text: CanonicalText,
    segment_graph: SegmentGraph,
) -> StructureMetrics:
    input_signal = compute_input_structure_signal(canonical_text)
    output_signal = compute_output_structure_signal(segment_graph)

    input_density = float(input_signal["structural_density"])
    output_density = float(output_signal["structural_density"])
    if input_density <= 0.0:
        fidelity = 1.0 if output_density <= 0.0 else 0.0
    else:
        fidelity = round(min(input_density, output_density) / input_density, 6)
    gain = round(max(0.0, output_density - input_density), 6)

    segment_node_count = int(output_signal["segment_node_count"])
    edge_count = int(output_signal["edge_count"])
    structural_node_count = int(output_signal["structural_node_count"])
    graph_structuredness = round(
        (
            _ratio(edge_count, max(segment_node_count, 1) * 2)
            + _ratio(structural_node_count, max(segment_node_count, 1))
        )
        / 2,
        6,
    )

    return StructureMetrics(
        input_signal=input_signal,
        output_signal=output_signal,
        fidelity=fidelity,
        gain=gain,
        graph_structuredness=graph_structuredness,
    )


__all__ = [
    "StructureMetrics",
    "compute_input_structure_signal",
    "compute_output_structure_signal",
    "compute_structure_metrics",
]
