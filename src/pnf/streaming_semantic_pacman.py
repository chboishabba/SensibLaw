"""History-free streaming semantic transducer for direct PNF execution.

This module is an execution kernel, not a second semantic compiler.  The
semantic authority remains the existing direct PNF composer supplied through
callbacks.  The kernel only determines *when* already-authoritative semantic
work is performed.

The governing invariant mirrors the DASHI Agda owners:

    state(prefix ++ suffix)
      == continue_from(state(prefix), suffix)

Therefore a consumed parser prefix is never rescanned merely because later
parser observations arrive.  Only the current semantic authority and the
unresolved outward frontier are retained.

Formal owners (chboishabba/dashi_agda, agent/delta-native-parent-frontier):

- DASHI/Cognition/PNF/StreamingSemanticPacmanKernelExact.agda
- DASHI/Cognition/PNF/DeltaNativePNFDreamFlowExact.agda
- DASHI/Cognition/PNF/FibreSolverDeltaStreamExact.agda
- DASHI/Cognition/PNF/DirectDeltaCompilerArchitectureExact.agda
- DASHI/Cognition/PNF/DirectStreamingRoadmapSynthesisExact.agda

The literal "80% solved at parser EOF" idea is an empirical target, never a
semantic theorem.  ``StreamingCompletionReceipt`` records the quantities needed
to measure that target without changing compiler semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, Iterable, TypeVar

EventT = TypeVar("EventT")
AuthorityT = TypeVar("AuthorityT")
DeltaT = TypeVar("DeltaT")
FrontierT = TypeVar("FrontierT")


@dataclass(frozen=True, slots=True)
class StreamingCompletionReceipt:
    """Empirical work accounting for one streaming semantic run.

    ``stream_work_units`` counts work completed while parser observations were
    consumed. ``tail_work_units`` counts work performed by the finalizer after
    the parser/event stream closed.  Work units are deliberately caller-defined
    so wall-clock, affected-node counts, delta counts, or another stable metric
    can be used without redefining the kernel.
    """

    events_consumed: int
    stream_work_units: int
    tail_work_units: int
    final_frontier_size: int

    @property
    def total_work_units(self) -> int:
        return self.stream_work_units + self.tail_work_units

    @property
    def stream_completion_fraction(self) -> float:
        total = self.total_work_units
        if total == 0:
            return 1.0
        return self.stream_work_units / total


@dataclass(frozen=True, slots=True)
class StreamingSemanticSnapshot(Generic[AuthorityT, FrontierT]):
    """The complete retained state after consuming a parser prefix.

    No parser-event history is retained.  A future suffix must continue from
    this state rather than replaying the prefix.
    """

    authority: AuthorityT
    frontier: FrontierT
    events_consumed: int
    stream_work_units: int


class StreamingSemanticPacman(
    Generic[EventT, AuthorityT, DeltaT, FrontierT]
):
    """Consume parser observations into current authority plus open frontier.

    Callbacks adapt the existing semantic owners into this execution strategy:

    ``emit_delta``
        Produce the ordinary semantic delta for one newly available parser
        event/fibre.  This must call existing semantic composition machinery;
        it must not invent another graph semantics.

    ``apply_delta``
        Apply that delta to the current semantic authority.

    ``advance_frontier``
        Update unresolved forward dependencies after the delta is applied.
        Resolved work should disappear from this carrier immediately.

    ``measure_stream_work``
        Return empirical work units performed for this event.  The value is
        diagnostic only and cannot alter semantic state.

    ``finalize_frontier``
        Resolve only the remaining outward frontier at stream close.  It
        returns ``(final_authority, final_frontier, tail_work_units)``.
    """

    def __init__(
        self,
        *,
        initial_authority: AuthorityT,
        initial_frontier: FrontierT,
        emit_delta: Callable[[EventT, AuthorityT, FrontierT], DeltaT],
        apply_delta: Callable[[AuthorityT, DeltaT], AuthorityT],
        advance_frontier: Callable[
            [FrontierT, EventT, DeltaT, AuthorityT], FrontierT
        ],
        measure_stream_work: Callable[[EventT, DeltaT, AuthorityT, FrontierT], int],
        finalize_frontier: Callable[
            [AuthorityT, FrontierT], tuple[AuthorityT, FrontierT, int]
        ],
        frontier_size: Callable[[FrontierT], int],
    ) -> None:
        self._snapshot = StreamingSemanticSnapshot(
            authority=initial_authority,
            frontier=initial_frontier,
            events_consumed=0,
            stream_work_units=0,
        )
        self._emit_delta = emit_delta
        self._apply_delta = apply_delta
        self._advance_frontier = advance_frontier
        self._measure_stream_work = measure_stream_work
        self._finalize_frontier = finalize_frontier
        self._frontier_size = frontier_size

    @property
    def snapshot(self) -> StreamingSemanticSnapshot[AuthorityT, FrontierT]:
        return self._snapshot

    def consume(self, event: EventT) -> StreamingSemanticSnapshot[AuthorityT, FrontierT]:
        """Consume one newly available parser event exactly once."""

        current = self._snapshot
        delta = self._emit_delta(event, current.authority, current.frontier)
        authority = self._apply_delta(current.authority, delta)
        frontier = self._advance_frontier(current.frontier, event, delta, authority)
        work = int(self._measure_stream_work(event, delta, authority, frontier))
        if work < 0:
            raise ValueError("stream work units must be non-negative")
        self._snapshot = StreamingSemanticSnapshot(
            authority=authority,
            frontier=frontier,
            events_consumed=current.events_consumed + 1,
            stream_work_units=current.stream_work_units + work,
        )
        return self._snapshot

    def consume_many(
        self, events: Iterable[EventT]
    ) -> StreamingSemanticSnapshot[AuthorityT, FrontierT]:
        """Associatively fuse a physical batch into the same ordered fold."""

        for event in events:
            self.consume(event)
        return self._snapshot

    def finalize(
        self,
    ) -> tuple[
        StreamingSemanticSnapshot[AuthorityT, FrontierT], StreamingCompletionReceipt
    ]:
        """Resolve only the residual outward frontier after stream close."""

        current = self._snapshot
        authority, frontier, tail_work = self._finalize_frontier(
            current.authority, current.frontier
        )
        tail_work = int(tail_work)
        if tail_work < 0:
            raise ValueError("tail work units must be non-negative")
        final = StreamingSemanticSnapshot(
            authority=authority,
            frontier=frontier,
            events_consumed=current.events_consumed,
            stream_work_units=current.stream_work_units,
        )
        self._snapshot = final
        receipt = StreamingCompletionReceipt(
            events_consumed=final.events_consumed,
            stream_work_units=final.stream_work_units,
            tail_work_units=tail_work,
            final_frontier_size=int(self._frontier_size(final.frontier)),
        )
        if receipt.final_frontier_size < 0:
            raise ValueError("frontier size must be non-negative")
        return final, receipt


__all__ = [
    "StreamingCompletionReceipt",
    "StreamingSemanticPacman",
    "StreamingSemanticSnapshot",
]
