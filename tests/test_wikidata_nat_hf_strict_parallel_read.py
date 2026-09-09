from __future__ import annotations

from threading import Event, Lock

from src.ontology.wikidata_nat_hf_strict_executor import (
    resolve_qids_via_hosted_partial_scan_strict,
)


class RecordingLimiter:
    def __init__(self) -> None:
        self._lock = Lock()
        self.calls = 0

    def acquire(self, tokens: float = 1.0) -> None:
        assert tokens == 1.0
        with self._lock:
            self.calls += 1


def _manifest() -> dict:
    return {
        "sections": {
            "nodeOfName": {
                "chunks": [
                    {
                        "chunkIndex": 0,
                        "lang": "wikidata",
                        "objectPath": "hf://wd/0",
                        "length": 10,
                    },
                    {
                        "chunkIndex": 1,
                        "lang": "wikidata",
                        "objectPath": "hf://wd/1",
                        "length": 20,
                    },
                    {
                        "chunkIndex": 2,
                        "lang": "wikidata",
                        "objectPath": "hf://wd/2",
                        "length": 30,
                    },
                ]
            }
        }
    }


def test_later_speculative_crash_cannot_defeat_earlier_serial_resolution() -> None:
    later_finished = Event()
    limiter = RecordingLimiter()

    def runner(_binary: str, payload: str, *, timeout_seconds: float) -> tuple[int, str]:
        assert timeout_seconds == 5.0
        if "nodeOfName=0" in payload:
            assert later_finished.wait(timeout=2.0)
            return 0, "SL_NAT_PROBE|Q1|\nNode ID: 100\n"
        if "nodeOfName=1" in payload:
            later_finished.set()
            return -11, ""
        raise AssertionError(payload)

    receipt = resolve_qids_via_hosted_partial_scan_strict(
        _manifest(),
        ["Q1"],
        zelph_bin="/fixture/zelph",
        timeout_seconds=5.0,
        repl_runner=runner,
        worker_budget=2,
        rate_limiter=limiter,
    )

    assert receipt["status"] == "complete"
    assert receipt["resolved_qids"] == {"Q1": 100}
    assert receipt["resolved_qid_chunks"] == {"Q1": 0}
    assert receipt["failure"] is None
    assert receipt["semantic_chunk_count_committed"] == 1
    assert receipt["semantic_stopping_frontier_chunk"] == 0
    assert receipt["late_completions"] == 1
    assert receipt["chunks_not_launched_after_stop"] == 1
    assert limiter.calls == receipt["chunks_launched"] == 2
    assert receipt["peak_in_flight"] == 2


def test_later_crash_is_failure_when_serial_path_reaches_it() -> None:
    limiter = RecordingLimiter()

    def runner(_binary: str, payload: str, *, timeout_seconds: float) -> tuple[int, str]:
        assert timeout_seconds == 5.0
        if "nodeOfName=0" in payload:
            return 0, "SL_NAT_PROBE|Q1|\nError in line: No node found with name 'Q1'\n"
        if "nodeOfName=1" in payload:
            return -11, ""
        raise AssertionError(payload)

    receipt = resolve_qids_via_hosted_partial_scan_strict(
        _manifest(),
        ["Q1"],
        zelph_bin="/fixture/zelph",
        timeout_seconds=5.0,
        repl_runner=runner,
        worker_budget=2,
        rate_limiter=limiter,
    )

    assert receipt["status"] == "engine_failed"
    assert receipt["failure"]["signal_name"] == "SIGSEGV"
    assert receipt["semantic_chunk_count_committed"] == 2
    assert receipt["semantic_stopping_frontier_chunk"] == 1
    assert receipt["unresolved_qids"] == ["Q1"]
    assert receipt["nonzero_exit_means_no_match"] is False
