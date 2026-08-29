from __future__ import annotations

from src.pnf.streaming_semantic_pacman import StreamingSemanticPacman


def _kernel() -> StreamingSemanticPacman[int, tuple[int, ...], int, tuple[int, ...]]:
    def emit_delta(
        event: int, authority: tuple[int, ...], frontier: tuple[int, ...]
    ) -> int:
        del authority, frontier
        return event

    def apply_delta(authority: tuple[int, ...], delta: int) -> tuple[int, ...]:
        return authority + (delta,)

    def advance_frontier(
        frontier: tuple[int, ...],
        event: int,
        delta: int,
        authority: tuple[int, ...],
    ) -> tuple[int, ...]:
        del delta, authority
        # Odd values model unresolved forward obligations; the next even value
        # resolves the oldest one.  The exact policy is irrelevant to the
        # kernel: only the bounded frontier is retained, never event history.
        if event % 2:
            return frontier + (event,)
        if frontier:
            return frontier[1:]
        return frontier

    def measure_stream_work(
        event: int,
        delta: int,
        authority: tuple[int, ...],
        frontier: tuple[int, ...],
    ) -> int:
        del event, delta, authority, frontier
        return 1

    def finalize_frontier(
        authority: tuple[int, ...], frontier: tuple[int, ...]
    ) -> tuple[tuple[int, ...], tuple[int, ...], int]:
        return authority, (), len(frontier)

    return StreamingSemanticPacman(
        initial_authority=(),
        initial_frontier=(),
        emit_delta=emit_delta,
        apply_delta=apply_delta,
        advance_frontier=advance_frontier,
        measure_stream_work=measure_stream_work,
        finalize_frontier=finalize_frontier,
        frontier_size=len,
    )


def test_prefix_then_suffix_matches_single_stream_fold() -> None:
    streamed = _kernel()
    streamed.consume_many((1, 2))
    prefix = streamed.snapshot
    assert prefix.authority == (1, 2)
    assert prefix.events_consumed == 2

    streamed.consume_many((3, 4, 5))

    fused = _kernel()
    fused.consume_many((1, 2, 3, 4, 5))

    assert streamed.snapshot == fused.snapshot


def test_kernel_retains_current_authority_and_frontier_not_event_history() -> None:
    kernel = _kernel()
    kernel.consume_many(range(1, 101))

    snapshot = kernel.snapshot
    assert snapshot.events_consumed == 100
    assert snapshot.authority == tuple(range(1, 101))
    # The synthetic dependency policy closes every odd obligation with the
    # following even event, so no historical parser-event queue survives.
    assert snapshot.frontier == ()


def test_finalizer_only_pays_for_remaining_frontier() -> None:
    kernel = _kernel()
    kernel.consume_many((1, 2, 3))

    final, receipt = kernel.finalize()

    assert final.authority == (1, 2, 3)
    assert final.frontier == ()
    assert receipt.events_consumed == 3
    assert receipt.stream_work_units == 3
    assert receipt.tail_work_units == 1
    assert receipt.final_frontier_size == 0
    assert receipt.stream_completion_fraction == 0.75


def test_completion_fraction_is_measurement_not_acceptance_semantics() -> None:
    kernel = _kernel()
    kernel.consume_many((1,))
    final, receipt = kernel.finalize()

    assert final.authority == (1,)
    assert receipt.stream_completion_fraction == 0.5
    # Nothing in the kernel rejects this for being below an aspirational 80%.
