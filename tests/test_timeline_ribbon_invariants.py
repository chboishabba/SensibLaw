from __future__ import annotations

from math import isclose

from hypothesis import given, settings, strategies as st

EPS = 1e-6


@st.composite
def ribbon_partition(draw):
    cuts = sorted(
        draw(
            st.lists(
                st.floats(
                    min_value=0.0,
                    max_value=1.0,
                    allow_nan=False,
                    allow_infinity=False,
                ),
                min_size=1,
                max_size=6,
            )
        )
    )
    points = [0.0] + cuts + [1.0]

    segments = []
    remaining_mass = 1.0
    for idx in range(len(points) - 1):
        t_start, t_end = points[idx], points[idx + 1]
        mass = draw(
            st.floats(
                min_value=0.0,
                max_value=remaining_mass,
                allow_nan=False,
                allow_infinity=False,
            )
        )
        remaining_mass -= mass
        segments.append({"t_start": t_start, "t_end": t_end, "mass": mass})

    total_mass = sum(seg["mass"] for seg in segments)
    for seg in segments:
        seg["width_norm"] = 0.0 if total_mass == 0 else seg["mass"] / total_mass

    return segments, total_mass


@given(ribbon_partition())
@settings(max_examples=200)
def test_ribbon_partition_covers_domain(segments_and_mass):
    segments, _ = segments_and_mass
    assert segments[0]["t_start"] == 0.0
    assert segments[-1]["t_end"] == 1.0


@given(ribbon_partition())
@settings(max_examples=200)
def test_ribbon_partition_ordered_non_overlapping(segments_and_mass):
    segments, _ = segments_and_mass
    for idx in range(len(segments) - 1):
        assert segments[idx]["t_end"] <= segments[idx + 1]["t_start"]


@given(ribbon_partition())
@settings(max_examples=200)
def test_conservation_of_width(segments_and_mass):
    segments, _ = segments_and_mass
    total_width = sum(seg["width_norm"] for seg in segments)
    assert isclose(total_width, 1.0, abs_tol=EPS) or total_width == 0.0


@given(ribbon_partition())
@settings(max_examples=200)
def test_split_additivity(segments_and_mass):
    segments, _ = segments_and_mass
    seg = segments[0]
    m1 = seg["mass"] * 0.4
    m2 = seg["mass"] * 0.6
    assert isclose(m1 + m2, seg["mass"], abs_tol=EPS)


@given(ribbon_partition())
@settings(max_examples=200)
def test_merge_additivity(segments_and_mass):
    segments, _ = segments_and_mass
    if len(segments) < 2:
        return
    merged_mass = segments[0]["mass"] + segments[1]["mass"]
    assert merged_mass >= segments[0]["mass"]
    assert merged_mass >= segments[1]["mass"]


@given(ribbon_partition())
@settings(max_examples=200)
def test_non_negativity(segments_and_mass):
    segments, total_mass = segments_and_mass
    assert total_mass >= 0.0
    for seg in segments:
        assert seg["mass"] >= 0.0
        assert seg["width_norm"] >= 0.0
