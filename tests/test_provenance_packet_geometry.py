from __future__ import annotations

import pytest

from src.policy.provenance_packet_geometry import (
    ensure_receipt_kinds,
    packet_header,
    receipt_dict,
    receipt_pair,
    receipt_rows,
)


def test_receipt_geometry_helpers_are_deterministic() -> None:
    assert receipt_pair("kind", "value") == ("kind", "value")
    assert receipt_dict("kind", "value") == {"kind": "kind", "value": "value"}
    assert receipt_rows([("kind", "value")]) == [{"kind": "kind", "value": "value"}]
    assert packet_header(version="v1", summary="sum", primary_count=2, source_family="family", route_target="route") == {
        "version": "v1",
        "summary": "sum",
        "primary_count": 2,
        "source_family": "family",
        "route_target": "route",
    }


def test_ensure_receipt_kinds_detects_missing_values() -> None:
    with pytest.raises(ValueError, match="missing provenance receipt kinds: confidence"):
        ensure_receipt_kinds([{"kind": "link_type", "value": "causal_dispute"}], required_kinds=["link_type", "confidence"])
