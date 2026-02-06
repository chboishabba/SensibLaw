from __future__ import annotations

from sensiblaw.ribbon.compute import compute_segments, compute_total_mass


def test_compute_segments_normalizes_widths():
    lens = {"lens_id": "time", "units": "seconds", "rho": {"op": "const", "value": 1}}
    signals = {"placeholder": [1.0] * 10}
    boundaries = [0, 5, 10]

    segments = compute_segments(lens, signals, boundaries)
    total_width = sum(seg.width_norm for seg in segments)

    assert segments[0].mass == 5.0
    assert segments[1].mass == 5.0
    assert total_width == 1.0
    assert compute_total_mass(segments) == 10.0
