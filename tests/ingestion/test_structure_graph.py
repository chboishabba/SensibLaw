import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.ingestion.media_adapter import PdfPageMediaAdapter, parse_canonical_text
from src.ingestion.structure_graph import build_segment_graph


def test_build_segment_graph_emits_root_contains_follows_and_heads_edges():
    adapter = PdfPageMediaAdapter(source_artifact_ref="graph-pdf")
    canonical = adapter.adapt(
        [
            {"heading": "Section 1", "text": "The organisation must keep records."},
            {"heading": "Section 2", "text": "The organisation may publish a summary."},
        ]
    )
    envelope = parse_canonical_text(canonical)

    graph = build_segment_graph(envelope)

    assert graph.graph_id.endswith(":segment_graph")
    assert [node.role for node in graph.nodes] == [
        "root",
        "heading",
        "body",
        "heading",
        "body",
    ]
    assert [edge.to_dict() for edge in graph.edges] == [
        {
            "edge_kind": "contains",
            "source_id": f"{envelope.envelope_id}:root",
            "target_id": f"{envelope.envelope_id}:segment:0",
        },
        {
            "edge_kind": "contains",
            "source_id": f"{envelope.envelope_id}:root",
            "target_id": f"{envelope.envelope_id}:segment:1",
        },
        {
            "edge_kind": "contains",
            "source_id": f"{envelope.envelope_id}:root",
            "target_id": f"{envelope.envelope_id}:segment:2",
        },
        {
            "edge_kind": "contains",
            "source_id": f"{envelope.envelope_id}:root",
            "target_id": f"{envelope.envelope_id}:segment:3",
        },
        {
            "edge_kind": "follows",
            "source_id": f"{envelope.envelope_id}:segment:0",
            "target_id": f"{envelope.envelope_id}:segment:1",
        },
        {
            "edge_kind": "follows",
            "source_id": f"{envelope.envelope_id}:segment:1",
            "target_id": f"{envelope.envelope_id}:segment:2",
        },
        {
            "edge_kind": "follows",
            "source_id": f"{envelope.envelope_id}:segment:2",
            "target_id": f"{envelope.envelope_id}:segment:3",
        },
        {
            "edge_kind": "heads",
            "source_id": f"{envelope.envelope_id}:segment:0",
            "target_id": f"{envelope.envelope_id}:segment:1",
        },
        {
            "edge_kind": "heads",
            "source_id": f"{envelope.envelope_id}:segment:2",
            "target_id": f"{envelope.envelope_id}:segment:3",
        },
    ]
