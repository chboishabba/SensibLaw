from __future__ import annotations

from src.fact_intake.control_plane import build_follow_queue_item, summarize_follow_queue
from src.review_geometry.reviewer_packets import (
    build_reviewer_packet,
    normalize_packet_chips,
    normalize_packet_detail_rows,
)


def test_reviewer_packet_helpers_are_deterministic() -> None:
    assert normalize_packet_chips(["a", "", "b"]) == ["a", "b"]
    assert normalize_packet_detail_rows([{"label": "L", "value": "V"}, {"label": "", "value": "skip"}]) == [
        {"label": "L", "value": "V"}
    ]
    assert build_reviewer_packet(
        item_id="item:1",
        title="Item",
        subtitle="sub",
        description="desc",
        conjecture_kind="kind",
        route_target="target",
        resolution_status="open",
        chips=["x", ""],
        detail_rows=[{"label": "L", "value": "V"}],
        extra={"note": "extra"},
    )["chips"] == ["x"]


def test_follow_queue_builders_delegate_to_shared_packet_geometry() -> None:
    item = build_follow_queue_item(
        item_id="item:1",
        title="Item",
        conjecture_kind="kind",
        route_target="target",
        resolution_status="open",
        chips=["chip"],
        detail_rows=[{"label": "L", "value": "V"}],
    )
    assert item["chips"] == ["chip"]
    assert item["detail_rows"] == [{"label": "L", "value": "V"}]
    assert summarize_follow_queue([item]) == {
        "queue_count": 1,
        "route_target_counts": {"target": 1},
        "resolution_status_counts": {"open": 1},
    }
