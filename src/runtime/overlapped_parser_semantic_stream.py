"""Bounded producer/consumer overlap for parser output and semantic consumption.

The parser is a physical producer of ordered events/partitions.  The semantic
consumer is supplied by the caller and remains the existing semantic authority.
This module only overlaps their execution; it does not reinterpret parser or
PNF meaning.

A queue bound prevents parser output from becoming retained history.  Completed
items are consumed in order, and the producer may be at most ``queue_size``
items ahead of semantic consumption.  Consumer cancellation is propagated back
to the producer so a failed semantic publication cannot strand a parser thread
blocked on a full queue.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from queue import Full, Queue
from threading import Event, Thread
from time import monotonic_ns
from typing import Any, Iterable, Iterator


Interval = tuple[int, int]


@dataclass(slots=True)
class ParserStreamActivity:
    """Mutable timing receipt populated by the parser producer."""

    intervals: list[Interval] = field(default_factory=list)
    finished_ns: int | None = None

    @property
    def active_ns(self) -> int:
        return sum(max(0, end - start) for start, end in self.intervals)


@dataclass(frozen=True, slots=True)
class ParsedStreamItem:
    doc: Any
    context: Any
    parser_interval: Interval


@dataclass(frozen=True, slots=True)
class _ProducerFailure:
    error: BaseException


_SENTINEL = object()


def stream_parsed_items(
    pipeline: Any,
    inputs: Iterable[tuple[str, Any]],
    *,
    batch_size: int,
    queue_size: int = 1,
    activity: ParserStreamActivity | None = None,
) -> Iterator[ParsedStreamItem]:
    """Yield parser results while the producer continues parsing ahead.

    ``pipeline`` is used only by the producer thread.  The caller consumes each
    completed result synchronously, normally by feeding it into the direct
    semantic kernel/publication path.  Ordering is exactly the ordering emitted
    by ``pipeline.pipe``.
    """

    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    if queue_size < 1:
        raise ValueError("queue_size must be positive")
    activity = activity or ParserStreamActivity()
    queue: Queue[ParsedStreamItem | _ProducerFailure | object] = Queue(
        maxsize=queue_size
    )
    stop = Event()

    def put_until_stopped(item: ParsedStreamItem | _ProducerFailure | object) -> bool:
        while not stop.is_set():
            try:
                queue.put(item, timeout=0.05)
                return True
            except Full:
                continue
        return False

    def produce() -> None:
        try:
            iterator = iter(
                pipeline.pipe(
                    inputs,
                    as_tuples=True,
                    batch_size=batch_size,
                    n_process=1,
                )
            )
            while not stop.is_set():
                started = monotonic_ns()
                try:
                    doc, context = next(iterator)
                except StopIteration:
                    activity.finished_ns = monotonic_ns()
                    break
                finished = monotonic_ns()
                interval = (started, finished)
                activity.intervals.append(interval)
                if not put_until_stopped(
                    ParsedStreamItem(
                        doc=doc,
                        context=context,
                        parser_interval=interval,
                    )
                ):
                    return
        except BaseException as error:
            activity.finished_ns = monotonic_ns()
            put_until_stopped(_ProducerFailure(error))
        finally:
            if activity.finished_ns is None:
                activity.finished_ns = monotonic_ns()
            put_until_stopped(_SENTINEL)

    producer = Thread(
        target=produce,
        name="sensiblaw-parser-semantic-producer",
        daemon=True,
    )
    producer.start()
    try:
        while True:
            item = queue.get()
            if item is _SENTINEL:
                break
            if isinstance(item, _ProducerFailure):
                raise item.error
            yield item
    finally:
        # If the consumer raises or stops iteration early, unblock a producer
        # waiting on the bounded queue rather than retaining parser history.
        stop.set()
        producer.join()
    if activity.finished_ns is None:
        activity.finished_ns = monotonic_ns()


__all__ = [
    "ParsedStreamItem",
    "ParserStreamActivity",
    "stream_parsed_items",
]
