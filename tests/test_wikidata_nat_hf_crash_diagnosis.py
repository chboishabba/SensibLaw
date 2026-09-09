from __future__ import annotations

from src.ontology.wikidata_nat_hf_crash_diagnosis import diagnose_hosted_partial_chunk


def _manifest() -> dict:
    return {
        "sections": {
            "nodeOfName": {
                "chunks": [
                    {
                        "chunkIndex": 0,
                        "lang": "wikidata",
                        "objectPath": "hf://wd/0",
                        "length": 123,
                    }
                ]
            }
        }
    }


def test_diagnosis_identifies_first_failing_stage() -> None:
    calls: list[str] = []

    def fake_runner(_binary: str, payload: str, *, timeout_seconds: float):
        assert timeout_seconds == 5.0
        calls.append(payload)
        if "meta-only" in payload:
            return 0, "Header-only manifest load complete.\n"
        if ".lang wikidata" not in payload:
            return -11, ""
        return -11, ""

    receipt = diagnose_hosted_partial_chunk(
        _manifest(),
        qid="Q10403939",
        chunk_index=0,
        zelph_bin="/fixture/zelph",
        timeout_seconds=5.0,
        repl_runner=fake_runner,
    )
    assert len(calls) == 4
    assert receipt["first_failure_stage"] == "node_of_name_chunk_load_only"
    assert receipt["stages"][0]["exit_code"] == 0
    assert receipt["stages"][1]["exit_code"] == -11
    assert receipt["stages"][1]["signal_name"] == "SIGSEGV"
    assert receipt["diagnostic_only"] is True
    assert receipt["source_support_paid"] is False


def test_diagnosis_can_localize_node_probe_failure() -> None:
    def fake_runner(_binary: str, payload: str, *, timeout_seconds: float):
        assert timeout_seconds == 5.0
        if ".node Q10403939" in payload:
            return -11, ""
        return 0, "ok\n"

    receipt = diagnose_hosted_partial_chunk(
        _manifest(),
        qid="Q10403939",
        chunk_index=0,
        zelph_bin="/fixture/zelph",
        timeout_seconds=5.0,
        repl_runner=fake_runner,
    )
    assert receipt["first_failure_stage"] == "node_of_name_chunk_plus_node_probe"
    assert [stage["exit_code"] for stage in receipt["stages"]] == [0, 0, 0, -11]
