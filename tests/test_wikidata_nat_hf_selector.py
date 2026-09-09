from __future__ import annotations

from src.ontology.wikidata_nat_hf_selector import (
    HF_MANIFEST_URL,
    HF_SELECTOR_EXECUTOR_ID,
    _execute_selector,
)


class _Response:
    def __init__(self, payload: dict, headers: dict | None = None) -> None:
        self._payload = payload
        self.headers = headers or {}

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def _selector() -> dict:
    return {
        "candidate_only": True,
        "full_reasoning_required": False,
        "operations": [
            "node_route_selection",
            "sparql_subset",
            "partial_loading",
            "qualifier_reference_import",
        ],
        "qids": ["Q10403939"],
        "properties": ["P5991", "P14143", "P854"],
        "required_outputs": [
            "statement_snapshot",
            "qualifier_snaks",
            "reference_snaks",
            "source_revision_lineage",
            "content_address",
        ],
    }


def _canonical_manifest(*, node_route_index: bool) -> dict:
    return {
        "manifestVersion": "zelph-hf-layout/v2",
        "createdAtUtc": "2026-06-30T17:54:09Z",
        "transport": {"primary": "hf-object-fetch"},
        "capabilities": {
            "selectedChunkRead": True,
            "nodeRouteIndex": node_route_index,
            "fullReasoningSafe": False,
        },
        "layoutPlan": {
            "isCanonical": True,
            "supportsNodeRouteIndex": node_route_index,
        },
        "sections": {
            "nodeOfName": {
                "chunks": [
                    {
                        "chunkIndex": 0,
                        "lang": "wikidata",
                        "objectPath": "hf://datasets/acrion/zelph/nodeOfName/chunk-0",
                        "length": 100,
                    }
                ]
            }
        },
    }


def _outputs() -> dict:
    return {
        "statement_snapshot": {"Q10403939": {"claims": {}}},
        "qualifier_snaks": {"Q10403939": {}},
        "reference_snaks": {"Q10403939": {}},
        "source_revision_lineage": {"Q10403939": {"revid": 1}},
        "content_address": "sha256:test",
    }


def test_missing_route_index_uses_online_partial_scan_instead_of_blocking() -> None:
    calls: list[tuple[str, float]] = []

    def fake_get(url: str, *, timeout: float) -> _Response:
        calls.append((url, timeout))
        return _Response(
            _canonical_manifest(node_route_index=False),
            {"ETag": '"manifest-etag"', "X-Repo-Commit": "hf-revision"},
        )

    scan_calls: list[list[str]] = []

    def partial_scan(_manifest: dict, qids: list[str]) -> dict:
        scan_calls.append(list(qids))
        return {
            "status": "complete",
            "requested_qids": qids,
            "resolved_qids": {"Q10403939": 4242},
            "unresolved_qids": [],
            "network_performed": True,
            "route_index_required": False,
        }

    fetch_calls: list[tuple[list[str], list[str]]] = []

    def statement_fetch(qids: list[str], properties: list[str]) -> dict:
        fetch_calls.append((list(qids), list(properties)))
        return _outputs()

    result = _execute_selector(
        _selector(),
        http_get=fake_get,
        timeout_seconds=3.0,
        partial_scan_resolver=partial_scan,
        statement_fetcher=statement_fetch,
    )
    assert calls == [(HF_MANIFEST_URL, 3.0)]
    assert scan_calls == [["Q10403939"]]
    assert fetch_calls == [(["Q10403939"], ["P14143", "P5991", "P854"])]
    assert result["executor_id"] == HF_SELECTOR_EXECUTOR_ID
    assert result["execution_outcome"] == "executed_with_output"
    assert result["outputs"] == _outputs()
    receipt = result["executor_receipt"]
    assert receipt["network_performed"] is True
    assert (
        receipt["transport_status"]
        == "executed_via_unrouted_hf_partial_scan_plus_wikidata_entity_export"
    )
    assert receipt["manifest_version"] == "zelph-hf-layout/v2"
    assert receipt["selected_chunk_read"] is True
    assert receipt["node_route_index"] is False
    assert receipt["partial_read"]["resolved_qids"] == {"Q10403939": 4242}


def test_incomplete_partial_scan_is_no_match_not_negative_evidence() -> None:
    def fake_get(_url: str, *, timeout: float) -> _Response:
        assert timeout == 3.0
        return _Response(_canonical_manifest(node_route_index=False))

    result = _execute_selector(
        _selector(),
        http_get=fake_get,
        timeout_seconds=3.0,
        partial_scan_resolver=lambda _manifest, qids: {
            "status": "partial",
            "requested_qids": qids,
            "resolved_qids": {},
            "unresolved_qids": qids,
            "network_performed": True,
        },
        statement_fetcher=lambda *_args: (_ for _ in ()).throw(
            AssertionError("statement fetch must not run")
        ),
    )
    assert result["execution_outcome"] == "executed_no_match"
    assert result["outputs"] == {}
    assert result["executor_receipt"]["transport_status"] == "online_partial_scan_incomplete"


def test_non_candidate_request_is_rejected_before_network() -> None:
    selector = _selector()
    selector["candidate_only"] = False
    called = False

    def fake_get(_url: str, *, timeout: float) -> _Response:
        nonlocal called
        called = True
        raise AssertionError(timeout)

    result = _execute_selector(selector, http_get=fake_get, timeout_seconds=3.0)
    assert called is False
    assert result["execution_outcome"] == "engine_failed"
    assert result["executor_receipt"]["network_performed"] is False
    assert result["executor_receipt"]["transport_status"] == "rejected_non_candidate_request"


def test_full_reasoning_request_is_rejected_before_network() -> None:
    selector = _selector()
    selector["full_reasoning_required"] = True

    result = _execute_selector(
        selector,
        http_get=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError()),
        timeout_seconds=3.0,
    )
    assert result["execution_outcome"] == "engine_failed"
    assert result["executor_receipt"]["network_performed"] is False
    assert result["executor_receipt"]["transport_status"] == "rejected_full_reasoning_request"


def test_routed_manifest_still_requires_exact_statement_source_fetch() -> None:
    def fake_get(_url: str, *, timeout: float) -> _Response:
        assert timeout == 3.0
        return _Response(_canonical_manifest(node_route_index=True))

    result = _execute_selector(
        _selector(),
        http_get=fake_get,
        timeout_seconds=3.0,
        statement_fetcher=lambda _qids, _properties: _outputs(),
    )
    assert result["execution_outcome"] == "executed_with_output"
    assert result["outputs"] == _outputs()
    assert (
        result["executor_receipt"]["transport_status"]
        == "executed_via_routed_hf_plus_wikidata_entity_export"
    )


def test_manifest_fetch_failure_is_receipted_as_unavailable_not_no_match() -> None:
    def fake_get(_url: str, *, timeout: float) -> _Response:
        assert timeout == 3.0
        raise RuntimeError("offline")

    result = _execute_selector(_selector(), http_get=fake_get, timeout_seconds=3.0)
    assert result["execution_outcome"] == "engine_unavailable"
    assert result["outputs"] == {}
    receipt = result["executor_receipt"]
    assert receipt["transport_status"] == "manifest_fetch_failed"
    assert receipt["network_performed"] is True
