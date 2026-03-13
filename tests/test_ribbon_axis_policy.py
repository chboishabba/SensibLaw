from __future__ import annotations

from src.sensiblaw.ribbon.axis_policy import (
    AxisPoint,
    detect_axis_lane_collisions,
    deterministic_2d_fallback,
)


def test_detect_axis_lane_collisions_reports_shared_slot() -> None:
    points = [
        AxisPoint(point_id="p1", time_bucket="2026-03-11T10", account_lane="acct:main", contact_lane="contact:alice"),
        AxisPoint(point_id="p2", time_bucket="2026-03-11T10", account_lane="acct:main", contact_lane="contact:alice"),
        AxisPoint(point_id="p3", time_bucket="2026-03-11T10", account_lane="acct:main", contact_lane="contact:bob"),
    ]
    collisions = detect_axis_lane_collisions(points)
    assert len(collisions) == 1
    first, second = collisions[0]
    assert first.point_id == "p1"
    assert second.point_id == "p2"


def test_deterministic_2d_fallback_is_order_stable() -> None:
    points_a = [
        AxisPoint(point_id="p2", time_bucket="2026-03-11T11", account_lane="acct:b", contact_lane="contact:bob"),
        AxisPoint(point_id="p1", time_bucket="2026-03-11T10", account_lane="acct:a", contact_lane="contact:alice"),
    ]
    points_b = list(reversed(points_a))
    out_a = deterministic_2d_fallback(points_a)
    out_b = deterministic_2d_fallback(points_b)
    assert out_a == out_b
    assert [row["point_id"] for row in out_a] == ["p1", "p2"]


def test_deterministic_2d_fallback_preserves_contact_metadata() -> None:
    points = [
        AxisPoint(point_id="p1", time_bucket="2026-03-11T10", account_lane="acct:a", contact_lane="contact:alice"),
    ]
    out = deterministic_2d_fallback(points)
    assert len(out) == 1
    row = out[0]
    assert row["contact_lane"] == "contact:alice"
    assert row["account_lane"] == "acct:a"
    assert row["time_bucket"] == "2026-03-11T10"
