from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from functools import lru_cache
from typing import Any

import requests

from src.policy.carriers.canonical import canonical_sha256


HF_SELECTOR_EXECUTOR_ID = "sensiblaw.nat_hf_selector.v0_1"
HF_DATASET = "acrion/zelph"
HF_MANIFEST_PATH = "wikidata-20260309-all/wikidata-20260309-all.hf-v2.json"
HF_MANIFEST_URL = (
    "https://huggingface.co/datasets/"
    + HF_DATASET
    + "/resolve/main/"
    + HF_MANIFEST_PATH
)

HttpGet = Callable[..., Any]


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _text_list(values: Any) -> list[str]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes, bytearray)):
        return []
    return sorted({_text(value) for value in values if _text(value)})


def _executor_receipt(
    *,
    transport_status: str,
    manifest: Mapping[str, Any] | None,
    headers: Mapping[str, Any] | None,
    network_performed: bool,
    detail: str,
) -> dict[str, Any]:
    manifest_payload = dict(manifest or {})
    response_headers = dict(headers or {})
    return {
        "network_performed": network_performed,
        "transport": "hf-object-fetch",
        "dataset": HF_DATASET,
        "manifest_path": HF_MANIFEST_PATH,
        "manifest_url": HF_MANIFEST_URL,
        "transport_status": transport_status,
        "detail": detail,
        "manifest_version": _text(manifest_payload.get("manifestVersion")),
        "manifest_created_at_utc": _text(manifest_payload.get("createdAtUtc")),
        "manifest_digest": (
            "sha256:" + canonical_sha256(manifest_payload) if manifest_payload else ""
        ),
        "manifest_etag": _text(
            response_headers.get("ETag")
            or response_headers.get("etag")
            or response_headers.get("X-Linked-ETag")
            or response_headers.get("x-linked-etag")
        ),
        "manifest_revision": _text(
            response_headers.get("X-Repo-Commit")
            or response_headers.get("x-repo-commit")
        ),
        "node_route_index": bool(
            (manifest_payload.get("capabilities") or {}).get("nodeRouteIndex", False)
        ),
        "selected_chunk_read": bool(
            (manifest_payload.get("capabilities") or {}).get("selectedChunkRead", False)
        ),
        "full_reasoning_safe": bool(
            (manifest_payload.get("capabilities") or {}).get("fullReasoningSafe", False)
        ),
        "canonical_layout": bool(
            (manifest_payload.get("layoutPlan") or {}).get("isCanonical", False)
        ),
    }


def _fetch_manifest(*, http_get: HttpGet, timeout_seconds: float) -> tuple[dict[str, Any], Mapping[str, Any]]:
    response = http_get(HF_MANIFEST_URL, timeout=timeout_seconds)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, Mapping):
        raise ValueError("HF manifest response must be a mapping")
    return dict(payload), dict(getattr(response, "headers", {}) or {})


@lru_cache(maxsize=1)
def _fetch_manifest_cached() -> tuple[dict[str, Any], dict[str, Any]]:
    manifest, headers = _fetch_manifest(http_get=requests.get, timeout_seconds=30.0)
    return dict(manifest), dict(headers)


def _execute_selector(
    selector: Mapping[str, Any],
    *,
    http_get: HttpGet,
    timeout_seconds: float,
) -> dict[str, Any]:
    operations = _text_list(selector.get("operations"))
    qids = _text_list(selector.get("qids"))
    properties = _text_list(selector.get("properties"))

    if not bool(selector.get("candidate_only")):
        return {
            "executor_id": HF_SELECTOR_EXECUTOR_ID,
            "execution_outcome": "engine_failed",
            "executor_receipt": _executor_receipt(
                transport_status="rejected_non_candidate_request",
                manifest=None,
                headers=None,
                network_performed=False,
                detail="HF selector only accepts candidate-only acquisition requests.",
            ),
            "outputs": {},
        }
    if bool(selector.get("full_reasoning_required")):
        return {
            "executor_id": HF_SELECTOR_EXECUTOR_ID,
            "execution_outcome": "engine_failed",
            "executor_receipt": _executor_receipt(
                transport_status="rejected_full_reasoning_request",
                manifest=None,
                headers=None,
                network_performed=False,
                detail="Canonical HF transport does not advertise fullReasoningSafe.",
            ),
            "outputs": {},
        }
    if not qids or not properties:
        return {
            "executor_id": HF_SELECTOR_EXECUTOR_ID,
            "execution_outcome": "engine_failed",
            "executor_receipt": _executor_receipt(
                transport_status="rejected_unbounded_or_empty_selector",
                manifest=None,
                headers=None,
                network_performed=False,
                detail="Selector must name bounded QIDs and properties.",
            ),
            "outputs": {},
        }

    try:
        manifest, headers = _fetch_manifest(
            http_get=http_get,
            timeout_seconds=timeout_seconds,
        )
    except Exception as exc:  # requests and JSON/contract failures remain receipt-visible
        return {
            "executor_id": HF_SELECTOR_EXECUTOR_ID,
            "execution_outcome": "engine_unavailable",
            "executor_receipt": _executor_receipt(
                transport_status="manifest_fetch_failed",
                manifest=None,
                headers=None,
                network_performed=True,
                detail=f"{type(exc).__name__}: {exc}",
            ),
            "outputs": {},
        }

    return _evaluate_manifest(selector, manifest=manifest, headers=headers)


def _evaluate_manifest(
    selector: Mapping[str, Any],
    *,
    manifest: Mapping[str, Any],
    headers: Mapping[str, Any],
) -> dict[str, Any]:
    operations = _text_list(selector.get("operations"))
    capabilities = manifest.get("capabilities")
    capabilities = capabilities if isinstance(capabilities, Mapping) else {}
    layout = manifest.get("layoutPlan")
    layout = layout if isinstance(layout, Mapping) else {}
    transport = manifest.get("transport")
    transport = transport if isinstance(transport, Mapping) else {}

    common_receipt = {
        "manifest": manifest,
        "headers": headers,
        "network_performed": True,
    }

    if _text(manifest.get("manifestVersion")) != "zelph-hf-layout/v2":
        return {
            "executor_id": HF_SELECTOR_EXECUTOR_ID,
            "execution_outcome": "engine_unavailable",
            "executor_receipt": _executor_receipt(
                transport_status="unsupported_manifest_version",
                detail="Nat selector currently requires canonical zelph-hf-layout/v2.",
                **common_receipt,
            ),
            "outputs": {},
        }
    if not bool(layout.get("isCanonical")):
        return {
            "executor_id": HF_SELECTOR_EXECUTOR_ID,
            "execution_outcome": "engine_unavailable",
            "executor_receipt": _executor_receipt(
                transport_status="manifest_not_canonical",
                detail="HF manifest is not marked canonical.",
                **common_receipt,
            ),
            "outputs": {},
        }
    if _text(transport.get("primary")) != "hf-object-fetch":
        return {
            "executor_id": HF_SELECTOR_EXECUTOR_ID,
            "execution_outcome": "engine_unavailable",
            "executor_receipt": _executor_receipt(
                transport_status="unsupported_transport",
                detail="HF manifest does not advertise hf-object-fetch as primary transport.",
                **common_receipt,
            ),
            "outputs": {},
        }
    if not bool(capabilities.get("selectedChunkRead")):
        return {
            "executor_id": HF_SELECTOR_EXECUTOR_ID,
            "execution_outcome": "engine_unavailable",
            "executor_receipt": _executor_receipt(
                transport_status="selected_chunk_read_unavailable",
                detail="Canonical manifest cannot satisfy bounded partial-loading requests.",
                **common_receipt,
            ),
            "outputs": {},
        }
    if "node_route_selection" in operations and not bool(capabilities.get("nodeRouteIndex")):
        return {
            "executor_id": HF_SELECTOR_EXECUTOR_ID,
            "execution_outcome": "engine_unavailable",
            "executor_receipt": _executor_receipt(
                transport_status="blocked_missing_node_route_index",
                detail=(
                    "Canonical HF v2 manifest is available, but QID-directed bounded "
                    "dispatch is blocked because nodeRouteIndex=false."
                ),
                **common_receipt,
            ),
            "outputs": {},
        }

    return {
        "executor_id": HF_SELECTOR_EXECUTOR_ID,
        "execution_outcome": "engine_unavailable",
        "executor_receipt": _executor_receipt(
            transport_status="selector_decode_adapter_not_implemented",
            detail=(
                "Manifest preflight passed, but SensibLaw does not yet own the "
                "QID/property-to-statement decode adapter required for the requested outputs."
            ),
            **common_receipt,
        ),
        "outputs": {},
    }


def hosted_hf_selector_executor(selector: Mapping[str, Any]) -> dict[str, Any]:
    """Preflight the canonical hosted Zelph/Wikidata HF manifest.

    This is a real network-backed selector executor, but it intentionally fails
    closed until the canonical manifest exposes the QID->shard routing needed by
    Nat's bounded node-route requests and the downstream decode adapter exists.
    It never invents statement/reference outputs from manifest metadata alone.
    """

    operations = _text_list(selector.get("operations"))
    qids = _text_list(selector.get("qids"))
    properties = _text_list(selector.get("properties"))
    if not bool(selector.get("candidate_only")) or bool(
        selector.get("full_reasoning_required")
    ) or not operations or not qids or not properties:
        return _execute_selector(selector, http_get=requests.get, timeout_seconds=30.0)

    try:
        manifest, headers = _fetch_manifest_cached()
    except Exception as exc:
        return {
            "executor_id": HF_SELECTOR_EXECUTOR_ID,
            "execution_outcome": "engine_unavailable",
            "executor_receipt": _executor_receipt(
                transport_status="manifest_fetch_failed",
                manifest=None,
                headers=None,
                network_performed=True,
                detail=f"{type(exc).__name__}: {exc}",
            ),
            "outputs": {},
        }
    return _evaluate_manifest(selector, manifest=manifest, headers=headers)


__all__ = [
    "HF_DATASET",
    "HF_MANIFEST_PATH",
    "HF_MANIFEST_URL",
    "HF_SELECTOR_EXECUTOR_ID",
    "hosted_hf_selector_executor",
]
