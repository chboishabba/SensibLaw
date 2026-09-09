from __future__ import annotations

from src.ontology.wikidata_nat_hf_strict_executor import (
    _strict_evaluate,
    resolve_qids_via_hosted_partial_scan_strict,
)


def _manifest() -> dict:
    return {
        "manifestVersion": "zelph-hf-layout/v2",
        "createdAtUtc": "2026-06-30T17:54:09Z",
        "transport": {"primary": "hf-object-fetch"},
        "capabilities": {
            "selectedChunkRead": True,
            "nodeRouteIndex": False,
            "fullReasoningSafe": False,
        },
        "layoutPlan": {"isCanonical": True, "supportsNodeRouteIndex": False},
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
                ]
            }
        },
    }


def _selector() -> dict:
    return {
        "candidate_only": True,
        "full_reasoning_required": False,
        "operations": ["node_route_selection", "partial_loading"],
        "qids": ["Q1"],
        "properties": ["P5991", "P854"],
        "required_outputs": [
            "statement_snapshot",
            "qualifier_snaks",
            "reference_snaks",
            "source_revision_lineage",
            "content_address",
        ],
    }


def test_strict_plain_node_id_resolves_and_retains_chunk_cache_seed() -> None:
    calls = 0

    def found(_binary: str, _payload: str, *, timeout_seconds: float):
        nonlocal calls
        assert timeout_seconds == 5.0
        calls += 1
        return 0, "SL_NAT_PROBE|Q1|\nNode ID: 123\n"

    receipt = resolve_qids_via_hosted_partial_scan_strict(
        _manifest(),
        ["Q1"],
        zelph_bin="/fixture/zelph",
        timeout_seconds=5.0,
        repl_runner=found,
    )
    assert calls == 1
    assert receipt["status"] == "complete"
    assert receipt["resolved_qids"] == {"Q1": 123}
    assert receipt["resolved_qid_chunks"] == {"Q1": 0}
    assert receipt["qid_route_cache_seed"] == {
        "Q1": {"zelph_node_id": 123, "node_of_name_chunk": 0}
    }
    assert receipt["unresolved_qids"] == []
    assert receipt["node_id_success_surface"] == "marker_scoped_Node_ID"


def test_sigsegv_stops_after_first_chunk_and_is_not_no_match() -> None:
    calls = 0

    def crashed(_binary: str, _payload: str, *, timeout_seconds: float):
        nonlocal calls
        assert timeout_seconds == 5.0
        calls += 1
        return -11, ""

    receipt = resolve_qids_via_hosted_partial_scan_strict(
        _manifest(),
        ["Q1"],
        zelph_bin="/fixture/zelph",
        timeout_seconds=5.0,
        repl_runner=crashed,
    )
    assert calls == 1
    assert receipt["status"] == "engine_failed"
    assert receipt["chunk_count_scanned"] == 1
    assert receipt["clean_chunk_count"] == 0
    assert receipt["unresolved_qids"] == ["Q1"]
    assert receipt["nonzero_exit_means_no_match"] is False
    failure = receipt["failure"]
    assert failure["exit_code"] == -11
    assert failure["termination_kind"] == "signal"
    assert failure["signal_number"] == 11
    assert failure["signal_name"] == "SIGSEGV"


def test_clean_exhaustion_remains_partial_not_engine_failure() -> None:
    def clean_absent(_binary: str, _payload: str, *, timeout_seconds: float):
        assert timeout_seconds == 5.0
        return 0, "SL_NAT_PROBE|Q1|\nError in line: No node found with name 'Q1'\n"

    receipt = resolve_qids_via_hosted_partial_scan_strict(
        _manifest(),
        ["Q1"],
        zelph_bin="/fixture/zelph",
        timeout_seconds=5.0,
        repl_runner=clean_absent,
    )
    assert receipt["status"] == "partial"
    assert receipt["chunk_count_scanned"] == 2
    assert receipt["clean_chunk_count"] == 2
    assert receipt["failure"] is None
    assert receipt["qid_route_cache_seed"] == {}


def test_selector_maps_crash_to_engine_failed() -> None:
    import src.ontology.wikidata_nat_hf_strict_executor as strict

    original = strict.resolve_qids_via_hosted_partial_scan_strict
    strict.resolve_qids_via_hosted_partial_scan_strict = lambda _manifest, qids: {
        "status": "engine_failed",
        "requested_qids": qids,
        "resolved_qids": {},
        "unresolved_qids": qids,
        "network_performed": True,
        "failure": {
            "failure_kind": "zelph_process_failed",
            "exit_code": -11,
            "signal_name": "SIGSEGV",
        },
    }
    try:
        result = _strict_evaluate(_selector(), manifest=_manifest(), headers={})
    finally:
        strict.resolve_qids_via_hosted_partial_scan_strict = original

    assert result["execution_outcome"] == "engine_failed"
    assert result["outputs"] == {}
    assert result["executor_receipt"]["transport_status"] == "online_partial_scan_process_failed"
    assert "SIGSEGV" in result["executor_receipt"]["detail"]


def test_runner_exception_is_engine_unavailable() -> None:
    def unavailable(_binary: str, _payload: str, *, timeout_seconds: float):
        assert timeout_seconds == 5.0
        raise TimeoutError("probe timed out")

    receipt = resolve_qids_via_hosted_partial_scan_strict(
        _manifest(),
        ["Q1"],
        zelph_bin="/fixture/zelph",
        timeout_seconds=5.0,
        repl_runner=unavailable,
    )
    assert receipt["status"] == "engine_unavailable"
    assert receipt["chunk_count_scanned"] == 1
    assert receipt["failure"]["failure_kind"] == "runner_exception"
