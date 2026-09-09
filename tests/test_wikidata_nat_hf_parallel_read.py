from __future__ import annotations

from threading import Event, Lock

from src.ontology.wikidata_nat_hf_partial_read import resolve_qids_via_hosted_partial_scan


class RecordingLimiter:
    def __init__(self) -> None:
        self._lock = Lock()
        self.calls = 0

    def acquire(self, tokens: float = 1.0) -> None:
        assert tokens == 1.0
        with self._lock:
            self.calls += 1


def _manifest(chunk_indices: list[int]) -> dict:
    return {
        "sections": {
            "nodeOfName": {
                "chunks": [
                    {
                        "chunkIndex": chunk_index,
                        "lang": "wikidata",
                        "objectPath": f"hf://wd/{chunk_index}",
                        "length": 10,
                    }
                    for chunk_index in chunk_indices
                ]
            }
        }
    }


def test_parallel_completion_order_does_not_own_canonical_qid_resolution() -> None:
    """The lower serial chunk wins even when a higher chunk completes first."""

    higher_completed = Event()
    limiter = RecordingLimiter()

    def fake_runner(_binary: str, payload: str, *, timeout_seconds: float) -> tuple[int, str]:
        assert timeout_seconds == 5.0
        if "nodeOfName=3" in payload:
            assert higher_completed.wait(timeout=2.0)
            return 0, "SL_NAT_PROBE|Q1|\nNode ID: 111\n"
        if "nodeOfName=7" in payload:
            higher_completed.set()
            return 0, "SL_NAT_PROBE|Q1|\nNode ID: 777\n"
        raise AssertionError(payload)

    receipt = resolve_qids_via_hosted_partial_scan(
        _manifest([3, 7, 11]),
        ["Q1"],
        zelph_bin="/fixture/zelph",
        timeout_seconds=5.0,
        repl_runner=fake_runner,
        worker_budget=2,
        rate_limiter=limiter,
    )

    assert receipt["resolved_qids"] == {"Q1": 111}
    assert receipt["resolved_qid_chunks"] == {"Q1": 3}
    assert receipt["serial_stopping_frontier_chunk"] == 3
    assert receipt["chunks_not_launched_after_resolution"] == 1
    assert receipt["peak_in_flight"] == 2
    assert limiter.calls == receipt["chunks_launched"] == 2
    assert receipt["rate_limit_policy"]["shared_across_workers"] is True


def test_parallel_and_serial_schedules_have_same_canonical_resolution_ref() -> None:
    limiter_parallel = RecordingLimiter()
    limiter_serial = RecordingLimiter()

    def fake_runner(_binary: str, payload: str, *, timeout_seconds: float) -> tuple[int, str]:
        del timeout_seconds
        if "nodeOfName=3" in payload:
            return 0, "SL_NAT_PROBE|Q1|\nNode ID: 101\nSL_NAT_PROBE|Q2|\nError\n"
        if "nodeOfName=7" in payload:
            return 0, "SL_NAT_PROBE|Q1|\nNode ID: 999\nSL_NAT_PROBE|Q2|\nNode ID: 202\n"
        return 0, ""

    parallel = resolve_qids_via_hosted_partial_scan(
        _manifest([3, 7, 11]),
        ["Q1", "Q2"],
        zelph_bin="/fixture/zelph",
        repl_runner=fake_runner,
        worker_budget=3,
        rate_limiter=limiter_parallel,
    )
    serial = resolve_qids_via_hosted_partial_scan(
        _manifest([3, 7, 11]),
        ["Q1", "Q2"],
        zelph_bin="/fixture/zelph",
        repl_runner=fake_runner,
        worker_budget=1,
        rate_limiter=limiter_serial,
    )

    assert parallel["resolved_qids"] == serial["resolved_qids"] == {"Q1": 101, "Q2": 202}
    assert parallel["resolved_qid_chunks"] == serial["resolved_qid_chunks"] == {
        "Q1": 3,
        "Q2": 7,
    }
    assert parallel["canonical_resolution_ref"] == serial["canonical_resolution_ref"]
    assert parallel["execution_strategy"] == "bounded_rate_limited_parallel"
    assert serial["execution_strategy"] == "bounded_rate_limited_parallel"
