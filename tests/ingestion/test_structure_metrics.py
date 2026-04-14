import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.ingestion.media_adapter import PdfPageMediaAdapter, TextDocumentMediaAdapter, parse_canonical_text
from src.ingestion.structure_graph import build_segment_graph
from src.ingestion.structure_metrics import (
    compute_input_structure_signal,
    compute_output_structure_signal,
    compute_structure_metrics,
)


def test_compute_structure_metrics_reports_structural_density_for_heading_document():
    adapter = PdfPageMediaAdapter(source_artifact_ref="metrics-pdf")
    canonical = adapter.adapt(
        [
            {"heading": "Section 1", "text": "The organisation must keep records."},
            {"heading": "Section 2", "text": "The organisation may publish a summary."},
        ]
    )
    envelope = parse_canonical_text(canonical, include_structure_graph=True)
    graph = envelope.segment_graph or build_segment_graph(envelope)

    metrics = compute_structure_metrics(canonical, graph)

    assert metrics.input_signal == {
        "segment_count": 4,
        "segment_kind_counts": {"heading": 2, "paragraph": 2},
        "structural_segment_count": 2,
        "structural_density": 0.5,
    }
    assert metrics.output_signal["segment_node_count"] == 4
    assert metrics.output_signal["structural_node_count"] == 2
    assert metrics.output_signal["edge_kind_counts"] == {"contains": 4, "follows": 3, "heads": 2}
    assert metrics.fidelity == 1.0
    assert metrics.gain == 0.0
    assert metrics.graph_structuredness > 0.5


def test_compute_structure_metrics_keeps_flat_text_low_structure():
    adapter = TextDocumentMediaAdapter(source_artifact_ref="metrics-text")
    canonical = adapter.adapt("A plain paragraph without headings or lists.")
    envelope = parse_canonical_text(canonical, include_structure_graph=True)
    graph = envelope.segment_graph or build_segment_graph(envelope)

    input_signal = compute_input_structure_signal(canonical)
    output_signal = compute_output_structure_signal(graph)
    metrics = compute_structure_metrics(canonical, graph)

    assert input_signal == {
        "segment_count": 1,
        "segment_kind_counts": {"paragraph": 1},
        "structural_segment_count": 0,
        "structural_density": 0.0,
    }
    assert output_signal["segment_node_count"] == 1
    assert output_signal["structural_node_count"] == 0
    assert output_signal["edge_kind_counts"] == {"contains": 1}
    assert metrics.fidelity == 1.0
    assert metrics.gain == 0.0
    assert metrics.graph_structuredness == 0.25
