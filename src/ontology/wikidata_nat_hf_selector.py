from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from functools import lru_cache
from typing import Any

import requests

from src.ontology.wikidata_nat_hf_partial_read import (
    fetch_live_wikidata_statement_payload,
    resolve_qids_via_hosted_partial_scan,
)
from src.policy.carriers.canonical import canonical_sha256


HF_SELECTOR_EXECUTOR_ID = "sensiblaw.nat_hf_selector.v0_2"
HF_DATASET = "acrion/zelph"
HF_MANIFEST_PATH = "wikidata-20260309-all/wikidata-20260309-all.hf-v2.json"
HF_MANIFEST_URL = (
    "https://huggingface.co/datasets/"
    + HF_DATASET
    + "/resolve/main/"
    + HF_MANIFEST_PATH
)

HttpGet = Callable[..., Any]
PartialScanResolver = Callable[[Mapping[str, Any], Sequence[str]], Mapping[str, Any]]
StatementFetcher = Callable[[Sequence[str], Sequence[str]], Mapping[str, Any]]


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
    partial_read: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    manifest_payload = dict(manifest or {})
    response_headers = dict(headers or {})
    receipt = {
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
    if partial_read is not None:
        receipt["partial_read"] = dict(partial_read)
    return receipt


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


def _preflight_selector(selector: Mapping[str, Any]) -> tuple[list[str], list[str], list[str]] | dict[str, Any]:
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
    if not qids or not properties or not operations:
        return {
            "executor_id": HF_SELECTOR_EXECUTOR_ID,
            "execution_outcome": "engine_failed",
            "executor_receipt": _executor_receipt(
                transport_status="rejected_unbounded_or_empty_selector",
                manifest=None,
                headers=None,
                network_performed=False,
                detail="Selector must name bounded QIDs, properties, and operations.",
            ),
            "outputs": {},
        }
    return operations, qids, properties


def _evaluate_manifest(
    selector: Mapping[str, Any],
    *,
    manifest: Mapping[str, Any],
    headers: Mapping[str, Any],
    partial_scan_resolver: PartialScanResolver | None,
    statement_fetcher: StatementFetcher | None,
) -> dict[str, Any]:
    preflight = _preflight_selector(selector)
    if isinstance(preflight, dict):
        return preflight
    operations, qids, properties = preflight

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
                detail="Canonical manifest cannot satisfy partial-loading requests.",
                **common_receipt,
            ),
            "outputs": {},
        }

    partial_read: Mapping[str, Any] | None = None
    unresolved: list[str] = []
    qids_for_statement_fetch = list(qids)
    needs_unrouted_scan = (
        "node_route_selection" in operations
        and not bool(capabilities.get("nodeRouteIndex"))
    )
    if needs_unrouted_scan:
        if partial_scan_resolver is None:
            return {
                "executor_id": HF_SELECTOR_EXECUTOR_ID,
                "execution_outcome": "engine_unavailable",
                "executor_receipt": _executor_receipt(
                    transport_status="online_partial_scan_adapter_unavailable",
                    detail=(
                        "nodeRouteIndex=false, but selectedChunkRead=true. "
                        "Progress is allowed through an online nodeOfName shard scan; "
                        "no partial-scan adapter was supplied to this invocation."
                    ),
                    **common_receipt,
                ),
                "outputs": {},
            }
        try:
            partial_read = partial_scan_resolver(manifest, qids)
        except Exception as exc:
            return {
                "executor_id": HF_SELECTOR_EXECUTOR_ID,
                "execution_outcome": "engine_unavailable",
                "executor_receipt": _executor_receipt(
                    transport_status="online_partial_scan_failed",
                    detail=f"{type(exc).__name__}: {exc}",
                    partial_read=None,
                    **common_receipt,
                ),
                "outputs": {},
            }

        unresolved = _text_list(partial_read.get("unresolved_qids"))
        unresolved_set = set(unresolved)
        qids_for_statement_fetch = [qid for qid in qids if qid not in unresolved_set]
        if unresolved and not qids_for_statement_fetch:
            return {
                "executor_id": HF_SELECTOR_EXECUTOR_ID,
                "execution_outcome": "executed_no_match",
                "executor_receipt": _executor_receipt(
                    transport_status="online_partial_scan_incomplete_no_resolved_subset",
                    detail=(
                        "Hosted nodeOfName partial scan resolved none of the requested QIDs. "
                        "No negative-evidence claim is made."
                    ),
                    partial_read=partial_read,
                    **common_receipt,
                ),
                "outputs": {},
            }

    if statement_fetcher is None:
        return {
            "executor_id": HF_SELECTOR_EXECUTOR_ID,
            "execution_outcome": "engine_unavailable",
            "executor_receipt": _executor_receipt(
                transport_status="wikidata_statement_fetcher_unavailable",
                detail=(
                    "HF partial discovery succeeded, but exact Wikidata statement/"
                    "qualifier/reference source retrieval is not configured."
                ),
                partial_read=partial_read,
                **common_receipt,
            ),
            "outputs": {},
        }

    try:
        outputs = dict(statement_fetcher(qids_for_statement_fetch, properties))
    except Exception as exc:
        return {
            "executor_id": HF_SELECTOR_EXECUTOR_ID,
            "execution_outcome": "engine_unavailable",
            "executor_receipt": _executor_receipt(
                transport_status="wikidata_statement_fetch_failed",
                detail=f"{type(exc).__name__}: {exc}",
                partial_read=partial_read,
                **common_receipt,
            ),
            "outputs": {},
        }

    partial_subset = bool(unresolved)
    receipt = _executor_receipt(
        transport_status=(
            "executed_via_partial_identity_subset_plus_wikidata_entity_export"
            if partial_subset
            else (
                "executed_via_unrouted_hf_partial_scan_plus_wikidata_entity_export"
                if needs_unrouted_scan
                else "executed_via_routed_hf_plus_wikidata_entity_export"
            )
        ),
        detail=(
            (
                "Zelph/HF resolved only a subset of requested QIDs; exact Wikidata "
                "statement acquisition continued for that resolved subset. Unresolved "
                "QIDs remain live residuals and no absence claim is made."
            )
            if partial_subset
            else (
                "Zelph/HF supplies bounded graph discovery/identity confirmation; "
                "Wikidata entity export supplies exact statement, qualifier, reference, "
                "and revision source data. P854 verification remains downstream."
            )
        ),
        partial_read=partial_read,
        **common_receipt,
    )
    receipt["requested_qids"] = list(qids)
    receipt["statement_fetch_qids"] = list(qids_for_statement_fetch)
    receipt["unresolved_qids"] = list(unresolved)
    receipt["partial_identity_subset"] = partial_subset
    receipt["all_requested_qids_resolved"] = not partial_subset

    return {
        "executor_id": HF_SELECTOR_EXECUTOR_ID,
        "execution_outcome": "executed_with_output",
        "executor_receipt": receipt,
        "outputs": outputs,
    }


def _execute_selector(
    selector: Mapping[str, Any],
    *,
    http_get: HttpGet,
    timeout_seconds: float,
    partial_scan_resolver: PartialScanResolver | None = None,
    statement_fetcher: StatementFetcher | None = None,
) -> dict[str, Any]:
    preflight = _preflight_selector(selector)
    if isinstance(preflight, dict):
        return preflight
    try:
        manifest, headers = _fetch_manifest(
            http_get=http_get,
            timeout_seconds=timeout_seconds,
        )
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
    return _evaluate_manifest(
        selector,
        manifest=manifest,
        headers=headers,
        partial_scan_resolver=partial_scan_resolver,
        statement_fetcher=statement_fetcher,
    )


def hosted_hf_selector_executor(selector: Mapping[str, Any]) -> dict[str, Any]:
    """Run the live Nat acquisition path over hosted Zelph/HF partial reads.

    Missing node-route metadata is an optimization gap, not a correctness wall:
    this executor may scan hosted ``nodeOfName`` shards until the bounded QIDs
    resolve. Exact qualifier/reference/revision payloads are fetched for every
    QID that does resolve; one unresolved member no longer blocks progress for
    unrelated residuals in the same shared transport union. The dispatcher still
    keeps ``prerequisite_paid=false`` and external P854 verification downstream.
    """

    preflight = _preflight_selector(selector)
    if isinstance(preflight, dict):
        return preflight
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

    return _evaluate_manifest(
        selector,
        manifest=manifest,
        headers=headers,
        partial_scan_resolver=lambda current_manifest, qids: resolve_qids_via_hosted_partial_scan(
            current_manifest, qids
        ),
        statement_fetcher=lambda qids, properties: fetch_live_wikidata_statement_payload(
            qids, properties
        ),
    )


__all__ = [
    "HF_DATASET",
    "HF_MANIFEST_PATH",
    "HF_MANIFEST_URL",
    "HF_SELECTOR_EXECUTOR_ID",
    "hosted_hf_selector_executor",
]
