from __future__ import annotations

from threading import Event

import pytest

from src.runtime.overlapped_parser_semantic_stream import (
    ParserStreamActivity,
    stream_parsed_items,
)


class _FakePipeline:
    def __init__(self, values: tuple[tuple[object, object], ...]) -> None:
        self.values = values
        self.pipe_calls = 0
        self.batch_sizes: list[int] = []

    def pipe(
        self,
        inputs: object,
        *,
        as_tuples: bool,
        batch_size: int,
        n_process: int,
    ):
        assert as_tuples is True
        assert batch_size > 0
        assert n_process == 1
        tuple(inputs)
        self.pipe_calls += 1
        self.batch_sizes.append(batch_size)
        yield from self.values


class _FailingPipeline:
    def pipe(
        self,
        inputs: object,
        *,
        as_tuples: bool,
        batch_size: int,
        n_process: int,
    ):
        del inputs, as_tuples, batch_size, n_process
        yield "first", 1
        raise RuntimeError("parser exploded")


def test_stream_preserves_parser_order_and_records_eof() -> None:
    pipeline = _FakePipeline((("doc-a", "a"), ("doc-b", "b"), ("doc-c", "c")))
    activity = ParserStreamActivity()

    items = tuple(
        stream_parsed_items(
            pipeline,
            (("text", "context"),),
            batch_size=4,
            queue_size=1,
            activity=activity,
        )
    )

    assert [item.doc for item in items] == ["doc-a", "doc-b", "doc-c"]
    assert [item.context for item in items] == ["a", "b", "c"]
    assert pipeline.pipe_calls == 1
    assert pipeline.batch_sizes == [4]
    assert activity.effective_pipe_batch_size == 4
    assert len(activity.intervals) == 3
    assert activity.active_ns >= 0
    assert activity.finished_ns is not None


def test_pipe_batch_can_be_smaller_than_leased_batch(monkeypatch: pytest.MonkeyPatch) -> None:
    pipeline = _FakePipeline((("doc-a", "a"), ("doc-b", "b")))
    activity = ParserStreamActivity()
    monkeypatch.setenv("SENSIBLAW_STREAM_PIPE_BATCH_SIZE", "1")

    items = tuple(
        stream_parsed_items(
            pipeline,
            (("a", 1), ("b", 2), ("c", 3), ("d", 4)),
            batch_size=4,
            queue_size=1,
            activity=activity,
        )
    )

    assert [item.doc for item in items] == ["doc-a", "doc-b"]
    assert pipeline.batch_sizes == [1]
    assert activity.effective_pipe_batch_size == 1


def test_invalid_pipe_batch_override_fails_before_parser_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline = _FakePipeline(())
    monkeypatch.setenv("SENSIBLAW_STREAM_PIPE_BATCH_SIZE", "0")

    with pytest.raises(ValueError, match="SENSIBLAW_STREAM_PIPE_BATCH_SIZE"):
        tuple(stream_parsed_items(pipeline, (), batch_size=4))
    assert pipeline.pipe_calls == 0


def test_parser_failure_is_relayed_to_semantic_consumer() -> None:
    activity = ParserStreamActivity()
    iterator = stream_parsed_items(
        _FailingPipeline(),
        (("text", "context"),),
        batch_size=1,
        activity=activity,
    )

    first = next(iterator)
    assert first.doc == "first"
    with pytest.raises(RuntimeError, match="parser exploded"):
        next(iterator)
    assert activity.finished_ns is not None


def test_consumer_can_stop_early_without_waiting_for_unbounded_parser_history() -> None:
    release_second = Event()

    class BlockingPipeline:
        def pipe(
            self,
            inputs: object,
            *,
            as_tuples: bool,
            batch_size: int,
            n_process: int,
        ):
            del inputs, as_tuples, batch_size, n_process
            yield "first", 1
            release_second.wait(timeout=1.0)
            # More results than the queue can retain. Closing the consumer
            # must signal the producer instead of allowing this to deadlock.
            for ordinal in range(2, 20):
                yield f"doc-{ordinal}", ordinal

    iterator = stream_parsed_items(
        BlockingPipeline(),
        (("text", "context"),),
        batch_size=1,
        queue_size=1,
    )
    assert next(iterator).doc == "first"
    release_second.set()
    iterator.close()


def test_invalid_queue_and_batch_bounds_fail_before_starting_thread() -> None:
    pipeline = _FakePipeline(())
    with pytest.raises(ValueError, match="batch_size"):
        tuple(stream_parsed_items(pipeline, (), batch_size=0))
    with pytest.raises(ValueError, match="queue_size"):
        tuple(stream_parsed_items(pipeline, (), batch_size=1, queue_size=0))
