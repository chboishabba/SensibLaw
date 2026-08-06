from __future__ import annotations

from src.pnf.numeric_hyperfabric import MdlProfile
from src.storage.postgres.numeric_hierarchy_planner import (
    InterfaceSketch,
    plan_interface_segments,
)


def _sketch(
    ordinal: int,
    *,
    object_key: tuple[int, int],
    demand_key: tuple[int, int] | None = None,
) -> InterfaceSketch:
    return InterfaceSketch(
        region_id=100 + ordinal,
        interface_id=200 + ordinal,
        sequence_no=ordinal,
        start_char=ordinal * 100,
        end_char=(ordinal + 1) * 100,
        object_keys=frozenset((object_key,)),
        factor_keys=frozenset(),
        demand_keys=(
            frozenset((demand_key,))
            if demand_key is not None
            else frozenset()
        ),
        edge_count=0,
        encoded_byte_count=128,
        closure_rounds=1,
    )


def test_recurrence_compression_can_form_one_adaptive_block() -> None:
    sketches = (
        _sketch(0, object_key=(42, 0), demand_key=(7, 42)),
        _sketch(1, object_key=(42, 0), demand_key=(7, 42)),
    )
    result = plan_interface_segments(
        sketches,
        profile=MdlProfile(max_window=4, beam_width=3),
    )

    assert len(result.segments) == 1
    assert result.segments[0].start == 0
    assert result.segments[0].end == 2
    assert result.segments[0].measure.interface_cardinality == 2
    assert result.segments[0].measure.unresolved_count == 1
    assert result.evaluated_candidates <= result.asymptotic_bound


def test_merge_threshold_can_preserve_authored_boundaries() -> None:
    sketches = (
        _sketch(0, object_key=(10, 0)),
        _sketch(1, object_key=(20, 0)),
    )
    result = plan_interface_segments(
        sketches,
        profile=MdlProfile(
            max_window=4,
            beam_width=3,
            merge_threshold=100.0,
        ),
    )

    assert len(result.segments) == 2
    assert [(row.start, row.end) for row in result.segments] == [(0, 1), (1, 2)]
