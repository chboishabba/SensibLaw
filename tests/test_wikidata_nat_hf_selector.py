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
        "hfObjects": {
            "manifest": {"path": "hf://datasets/acrion/zelph/example.hf-v2.json"}
        },
        "sections": {},
    }


def test_current_canonical_shape_blocks_exactly_on_missing_node_route_index() -> None:
    calls: list[tuple[str, float]] = []

    def fake_get(url: str, *, timeout: float) -> _Response:
        calls.append((url, timeout))
        return _Response(
            _canonical_manifest(node_route_index=False),
            {"ETag": '"manifest-etag"', "X-Repo-Commit": "hf-revision"},
        )

    result = _execute_selector(_selector(), http_get=fake_get, timeout_seconds=3.0)
    assert calls == [(HF_MANIFEST_URL, 3.0)]
    assert result["executor_id"] == HF_SELECTOR_EXECUTOR_ID
    assert result["execution_outcome"] == "engine_unavailable"
    assert result["outputs"] == {}
    receipt = result["executor_receipt"]
    assert receipt["network_performed"] is True
    assert receipt["transport_status"] == "blocked_missing_node_route_index"
    assert receipt["manifest_version"] == "zelph-hf-layout/v2"
    assert receipt["canonical_layout"] is True
    assert receipt["selected_chunk_read"] is True
    assert receipt["node_route_index"] is False
    assert receipt["full_reasoning_safe"] is False
    assert receipt["manifest_revision"] == "hf-revision"
    assert receipt["manifest_digest"].startswith("sha256:")


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


def test_route_capability_does_not_fabricate_statement_outputs() -> None:
    def fake_get(_url: str, *, timeout: float) -> _Response:
        assert timeout == 3.0
        return _Response(_canonical_manifest(node_route_index=True))

    result = _execute_selector(_selector(), http_get=fake_get, timeout_seconds=3.0)
    assert result["execution_outcome"] == "engine_unavailable"
    assert result["outputs"] == {}
    assert (
        result["executor_receipt"]["transport_status"]
        == "selector_decode_adapter_not_implemented"
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
