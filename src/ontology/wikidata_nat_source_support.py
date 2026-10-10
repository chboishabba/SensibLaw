from __future__ import annotations

import hashlib
import ipaddress
import socket
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests

from src.policy.carriers.canonical import canonical_sha256


SOURCE_SUPPORT_RESIDUAL_SCHEMA_VERSION = "sl.nat_source_support_residual.v0_1"
SOURCE_FETCH_PLAN_SCHEMA_VERSION = "sl.nat_source_fetch_plan.v0_1"
SOURCE_FETCH_RECEIPT_SCHEMA_VERSION = "sl.nat_source_fetch_receipt.v0_1"
SOURCE_SUPPORT_RECOMPUTATION_SCHEMA_VERSION = "sl.nat_source_support_recomputation.v0_1"


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> Sequence[Any]:
    return (
        value
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))
        else ()
    )


def _batch_rows(batch: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = [row for row in _sequence(batch.get("rows")) if isinstance(row, Mapping)]
    rows.sort(key=lambda row: _text(row.get("row_ref")))
    return rows


def _reference_snaks(
    dispatch: Mapping[str, Any],
) -> dict[str, dict[str, list[Mapping[str, Any]]]]:
    merged: dict[str, dict[str, list[Mapping[str, Any]]]] = defaultdict(dict)
    for result in _sequence(dispatch.get("results")):
        if not isinstance(result, Mapping):
            continue
        refs = _mapping(_mapping(result.get("outputs")).get("reference_snaks"))
        for qid, statements in refs.items():
            if not isinstance(statements, Mapping):
                continue
            for statement_id, reference_list in statements.items():
                values = [
                    ref
                    for ref in _sequence(reference_list)
                    if isinstance(ref, Mapping)
                ]
                merged[_text(qid)][_text(statement_id)] = values
    return {qid: dict(statements) for qid, statements in merged.items()}


def _p854_urls(reference_list: Sequence[Mapping[str, Any]]) -> list[str]:
    urls: set[str] = set()
    for reference in reference_list:
        for snak in _sequence(reference.get("P854")):
            if not isinstance(snak, Mapping) or _text(snak.get("snaktype")) != "value":
                continue
            datavalue = _mapping(snak.get("datavalue"))
            value = datavalue.get("value")
            if isinstance(value, str) and value.strip():
                urls.add(value.strip())
    return sorted(urls)


def _source_residual(row: Mapping[str, Any], urls: Sequence[str]) -> dict[str, Any]:
    payload_without_ref = {
        "schema_version": SOURCE_SUPPORT_RESIDUAL_SCHEMA_VERSION,
        "source_row_ref": _text(row.get("row_ref")),
        "subject_qid": _text(row.get("qid")),
        "statement_reference": _text(row.get("statement_reference")),
        "source_property": _text(row.get("source_property")),
        "target_property": _text(row.get("target_property")),
        "consumer_reference": _text(row.get("row_ref")),
        "missing_coordinate": "sourceSupport",
        "reference_urls": sorted({_text(url) for url in urls if _text(url)}),
        "reference_presence": bool(urls),
        "content_acquisition_required": bool(urls),
        "proposition_support_evaluation_required": True,
        "authority_evaluation_required": True,
        "source_support_paid": False,
    }
    payload = dict(payload_without_ref)
    payload["residual_ref"] = "nat-source-support-residual:" + canonical_sha256(
        payload_without_ref
    )
    return payload


def build_source_fetch_plan(
    batch: Mapping[str, Any], coverage_dispatch: Mapping[str, Any]
) -> dict[str, Any]:
    """Join exact Nat rows to revision-derived P854 references and deduplicate fetch work.

    Source work may start only after the exact coverage tranche is closed. The plan
    is content-acquisition only: merely having or fetching a URL never pays source
    support, proposition correspondence, authority, or migration permission.
    """

    rows = _batch_rows(batch)
    if int(coverage_dispatch.get("coverage_residual_still_open_count", -1)) != 0:
        raise ValueError("source-support planning requires zero open coverage residuals")
    if int(coverage_dispatch.get("coverage_residual_paid_count", -1)) != len(rows):
        raise ValueError("source-support planning requires one paid coverage residual per row")

    refs = _reference_snaks(coverage_dispatch)
    residuals: list[dict[str, Any]] = []
    url_consumers: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        qid = _text(row.get("qid"))
        statement_reference = _text(row.get("statement_reference"))
        row_refs = refs.get(qid, {}).get(statement_reference, [])
        urls = _p854_urls(row_refs)
        residual = _source_residual(row, urls)
        residuals.append(residual)
        for url in urls:
            url_consumers[url].add(residual["residual_ref"])

    residuals.sort(key=lambda item: item["residual_ref"])
    fetches: list[dict[str, Any]] = []
    for url in sorted(url_consumers):
        payload_without_ref = {
            "url": url,
            "consumer_residual_refs": sorted(url_consumers[url]),
            "candidate_only": True,
            "content_acquisition_only": True,
            "source_support_payment_claimed": False,
            "semantic_promotion_authority": False,
        }
        payload = dict(payload_without_ref)
        payload["fetch_ref"] = "nat-source-fetch-demand:" + canonical_sha256(
            payload_without_ref
        )
        fetches.append(payload)

    payload_without_ref = {
        "schema_version": SOURCE_FETCH_PLAN_SCHEMA_VERSION,
        "source_batch_ref": _text(batch.get("batch_ref")),
        "source_coverage_dispatch_ref": _text(coverage_dispatch.get("dispatch_ref")),
        "row_count": len(residuals),
        "source_residual_count": len(residuals),
        "distinct_url_count": len(fetches),
        "residuals_without_p854_count": sum(
            1 for residual in residuals if not residual["reference_presence"]
        ),
        "source_residuals": residuals,
        "fetch_demands": fetches,
        "network_performed": False,
        "source_support_paid_count": 0,
        "consumer_verification_performed": False,
        "semantic_promotion_performed": False,
        "edits_performed": False,
    }
    payload = dict(payload_without_ref)
    payload["plan_ref"] = "nat-source-fetch-plan:" + canonical_sha256(
        payload_without_ref
    )
    return payload


def _public_http_url(url: str) -> tuple[bool, str]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False, "unsupported_or_missing_http_origin"
    host = parsed.hostname
    try:
        addresses = {
            item[4][0]
            for item in socket.getaddrinfo(
                host, parsed.port or (443 if parsed.scheme == "https" else 80)
            )
        }
    except OSError:
        return False, "dns_resolution_failed"
    for address in addresses:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            return False, "non_ip_dns_result"
        if not ip.is_global:
            return False, "non_public_network_target"
    return True, "public_http_origin"


def _bounded_body(response: Any, *, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    iterator = getattr(response, "iter_content", None)
    if callable(iterator):
        for raw in iterator(chunk_size=65536):
            chunk = bytes(raw or b"")
            total += len(chunk)
            if total > max_bytes:
                raise ValueError(f"source body exceeds max_bytes={max_bytes}")
            chunks.append(chunk)
        return b"".join(chunks)
    body = bytes(getattr(response, "content", b""))
    if len(body) > max_bytes:
        raise ValueError(f"source body exceeds max_bytes={max_bytes}")
    return body


def _persist_content_artifact(
    body: bytes,
    *,
    content_digest: str,
    artifact_store_dir: str | Path | None,
) -> tuple[bool, str]:
    """Persist one body under its verified SHA-256 identity.

    The returned path is relative to ``artifact_store_dir`` so receipts remain
    portable across machines. Existing blobs are re-hashed before reuse; a digest
    collision or corrupted store entry is a hard failure rather than a cache hit.
    """

    if artifact_store_dir is None:
        return False, ""
    if not content_digest.startswith("sha256:"):
        raise ValueError("content artifact persistence requires sha256 digest")
    digest_hex = content_digest.split(":", 1)[1]
    if len(digest_hex) != 64 or any(ch not in "0123456789abcdef" for ch in digest_hex):
        raise ValueError("invalid sha256 content digest")

    root = Path(artifact_store_dir)
    relpath = Path("sha256") / digest_hex[:2] / f"{digest_hex}.bin"
    path = root / relpath
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        existing = path.read_bytes()
        existing_digest = hashlib.sha256(existing).hexdigest()
        if existing_digest != digest_hex:
            raise ValueError("content-addressed artifact store digest mismatch")
        return True, relpath.as_posix()

    try:
        with path.open("xb") as handle:
            handle.write(body)
            handle.flush()
    except FileExistsError:
        existing = path.read_bytes()
        existing_digest = hashlib.sha256(existing).hexdigest()
        if existing_digest != digest_hex:
            raise ValueError("content-addressed artifact store digest mismatch")

    persisted = path.read_bytes()
    if hashlib.sha256(persisted).hexdigest() != digest_hex:
        raise ValueError("persisted source artifact failed digest verification")
    return True, relpath.as_posix()


def fetch_source_content(
    demand: Mapping[str, Any],
    *,
    http_get: Callable[..., Any] = requests.get,
    timeout_seconds: float = 30.0,
    max_bytes: int = 25_000_000,
    max_redirects: int = 5,
    artifact_store_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Acquire one external source artifact with bounded, redirect-safe telemetry.

    Every redirect target is independently checked against the public-network policy.
    Bodies are streamed under ``max_bytes``. When ``artifact_store_dir`` is supplied,
    successful bodies are persisted by SHA-256 and re-verified after persistence.
    This transport receipt can establish reachability/content acquisition/integrity
    only; it cannot establish that the source supports the proposition for the Nat row.
    """

    original_url = _text(demand.get("url"))
    current_url = original_url
    request_count = 0
    redirect_count = 0
    try:
        while True:
            allowed, policy = _public_http_url(current_url)
            if not allowed:
                payload_without_ref = {
                    "schema_version": SOURCE_FETCH_RECEIPT_SCHEMA_VERSION,
                    "fetch_ref": _text(demand.get("fetch_ref")),
                    "url": original_url,
                    "final_url": current_url,
                    "status": "rejected_by_network_policy",
                    "network_policy": policy,
                    "network_performed": request_count > 0,
                    "http_request_count": request_count,
                    "redirect_count": redirect_count,
                    "bytes_received": 0,
                    "cache_hits": 0,
                    "cache_misses": 1,
                    "content_digest": "",
                    "content_acquired": False,
                    "artifact_persisted": False,
                    "artifact_relpath": "",
                    "source_support_paid": False,
                }
                break

            response = http_get(
                current_url,
                timeout=timeout_seconds,
                allow_redirects=False,
                stream=True,
            )
            request_count += 1
            status_code = int(getattr(response, "status_code", 0) or 0)
            headers = _mapping(getattr(response, "headers", {}))
            if 300 <= status_code < 400:
                location = _text(headers.get("Location") or headers.get("location"))
                if not location:
                    raise ValueError("redirect response missing Location header")
                redirect_count += 1
                if redirect_count > max_redirects:
                    raise ValueError(f"source redirect count exceeds max_redirects={max_redirects}")
                current_url = urljoin(current_url, location)
                continue

            response.raise_for_status()
            body = _bounded_body(response, max_bytes=max_bytes)
            content_digest = "sha256:" + hashlib.sha256(body).hexdigest()
            artifact_persisted, artifact_relpath = _persist_content_artifact(
                body,
                content_digest=content_digest,
                artifact_store_dir=artifact_store_dir,
            )
            payload_without_ref = {
                "schema_version": SOURCE_FETCH_RECEIPT_SCHEMA_VERSION,
                "fetch_ref": _text(demand.get("fetch_ref")),
                "url": original_url,
                "final_url": current_url,
                "status": "content_acquired",
                "network_policy": policy,
                "network_performed": True,
                "http_status": status_code or 200,
                "http_request_count": request_count,
                "redirect_count": redirect_count,
                "content_type": _text(headers.get("Content-Type") or headers.get("content-type")),
                "bytes_received": len(body),
                "cache_hits": 0,
                "cache_misses": 1,
                "content_digest": content_digest,
                "content_acquired": True,
                "artifact_persisted": artifact_persisted,
                "artifact_relpath": artifact_relpath,
                "source_support_paid": False,
            }
            break
    except Exception as exc:
        payload_without_ref = {
            "schema_version": SOURCE_FETCH_RECEIPT_SCHEMA_VERSION,
            "fetch_ref": _text(demand.get("fetch_ref")),
            "url": original_url,
            "final_url": current_url,
            "status": "fetch_failed",
            "network_policy": "public_http_origin_checked_per_request",
            "network_performed": request_count > 0,
            "http_request_count": request_count,
            "redirect_count": redirect_count,
            "failure_type": type(exc).__name__,
            "failure_detail": str(exc),
            "bytes_received": 0,
            "cache_hits": 0,
            "cache_misses": 1,
            "content_digest": "",
            "content_acquired": False,
            "artifact_persisted": False,
            "artifact_relpath": "",
            "source_support_paid": False,
        }

    payload = dict(payload_without_ref)
    payload["receipt_ref"] = "nat-source-fetch-receipt:" + canonical_sha256(
        payload_without_ref
    )
    return payload


def recompute_source_support_observation(
    residual: Mapping[str, Any], receipts_by_url: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    urls = [
        url
        for url in _sequence(residual.get("reference_urls"))
        if isinstance(url, str)
    ]
    receipts = [receipts_by_url[url] for url in urls if url in receipts_by_url]
    any_acquired = any(bool(receipt.get("content_acquired")) for receipt in receipts)
    payload_without_ref = {
        "schema_version": SOURCE_SUPPORT_RECOMPUTATION_SCHEMA_VERSION,
        "live_residual_ref": _text(residual.get("residual_ref")),
        "source_row_ref": _text(residual.get("source_row_ref")),
        "subject_qid": _text(residual.get("subject_qid")),
        "statement_reference": _text(residual.get("statement_reference")),
        "reference_presence": bool(residual.get("reference_presence")),
        "reference_url_count": len(urls),
        "fetched_reference_count": len(receipts),
        "content_acquired": any_acquired,
        "content_integrity_observed": any(
            bool(_text(receipt.get("content_digest"))) for receipt in receipts
        ),
        "content_artifact_persisted": any(
            bool(receipt.get("artifact_persisted")) for receipt in receipts
        ),
        "proposition_support_evaluated": False,
        "authority_evaluated": False,
        "source_support_paid": False,
        "source_support_state": "open_requires_proposition_support_evaluation",
        "consumer_verification_performed": False,
        "semantic_promotion_performed": False,
        "migration_authority": False,
    }
    payload = dict(payload_without_ref)
    payload["recomputation_ref"] = (
        "nat-source-support-recomputation:" + canonical_sha256(payload_without_ref)
    )
    return payload


__all__ = [
    "SOURCE_FETCH_PLAN_SCHEMA_VERSION",
    "SOURCE_FETCH_RECEIPT_SCHEMA_VERSION",
    "SOURCE_SUPPORT_RECOMPUTATION_SCHEMA_VERSION",
    "SOURCE_SUPPORT_RESIDUAL_SCHEMA_VERSION",
    "build_source_fetch_plan",
    "fetch_source_content",
    "recompute_source_support_observation",
]
