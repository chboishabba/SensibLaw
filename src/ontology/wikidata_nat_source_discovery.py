from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol
from urllib.parse import urlparse
import re

from src.policy.carriers.canonical import canonical_sha256


SOURCE_DISCOVERY_PLAN_SCHEMA_VERSION = "sl.nat_source_discovery_plan.v0_1"
SOURCE_DISCOVERY_DEMAND_SCHEMA_VERSION = "sl.nat_source_discovery_demand.v0_1"
SOURCE_DISCOVERY_RECEIPT_SCHEMA_VERSION = "sl.nat_source_discovery_receipt.v0_1"
SOURCE_LOCATOR_CANDIDATE_SCHEMA_VERSION = "sl.nat_source_locator_candidate.v0_1"
SAME_SOURCE_IDENTITY_RECEIPT_SCHEMA_VERSION = "sl.nat_same_source_identity_receipt.v0_1"
ALTERNATE_SOURCE_FETCH_PLAN_SCHEMA_VERSION = "sl.nat_alternate_source_fetch_plan.v0_1"


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


def _persistent_identifier_hints(url: str) -> list[str]:
    hints: set[str] = set()
    decoded = url.replace("%3A", ":").replace("%2F", "/")
    for match in re.finditer(r"urn:[A-Za-z0-9][A-Za-z0-9:._/-]+", decoded, flags=re.I):
        hints.add(match.group(0).rstrip(".,);"))
    for match in re.finditer(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", decoded, flags=re.I):
        hints.add(match.group(0).rstrip(".,);"))
    return sorted(hints)


def _query_seeds(
    *,
    original_url: str,
    subject_qid: str,
    statement_reference: str,
    source_property: str,
    target_property: str,
) -> list[str]:
    seeds: list[str] = []
    for identifier in _persistent_identifier_hints(original_url):
        seeds.append(f'"{identifier}"')
    parsed = urlparse(original_url)
    basename = parsed.path.rsplit("/", 1)[-1].strip()
    if basename:
        seeds.append(f'"{basename}"')
    host = parsed.hostname or ""
    structural = " ".join(
        part
        for part in [host, subject_qid, statement_reference, source_property, target_property]
        if part
    )
    if structural:
        seeds.append(structural)
    seen: set[str] = set()
    ordered: list[str] = []
    for seed in seeds:
        if seed and seed not in seen:
            seen.add(seed)
            ordered.append(seed)
    return ordered


def build_source_discovery_plan(
    source_plan: Mapping[str, Any],
    source_dispatch: Mapping[str, Any],
) -> dict[str, Any]:
    """Compile discovery demands only for failed/unusable source locators.

    Discovery is a locator-recovery producer. It cannot pay source support, same-source
    identity, authority, or semantic promotion. Already-acquired source residuals are
    deliberately omitted from this plan.
    """

    residuals = {
        _text(item.get("residual_ref")): item
        for item in _sequence(source_plan.get("source_residuals"))
        if isinstance(item, Mapping) and _text(item.get("residual_ref"))
    }
    fetch_demands = {
        _text(item.get("fetch_ref")): item
        for item in _sequence(source_plan.get("fetch_demands"))
        if isinstance(item, Mapping) and _text(item.get("fetch_ref"))
    }
    failed_receipts = [
        item
        for item in _sequence(source_dispatch.get("fetch_receipts"))
        if isinstance(item, Mapping)
        and _text(item.get("status")) != "content_acquired"
    ]

    demands: list[dict[str, Any]] = []
    for receipt in failed_receipts:
        fetch_ref = _text(receipt.get("fetch_ref"))
        demand = _mapping(fetch_demands.get(fetch_ref))
        original_url = _text(receipt.get("url") or demand.get("url"))
        consumer_refs = sorted(
            {
                _text(ref)
                for ref in _sequence(demand.get("consumer_residual_refs"))
                if _text(ref)
            }
        )
        consumer_rows = [
            residuals[ref]
            for ref in consumer_refs
            if ref in residuals
        ]
        if not consumer_rows:
            continue
        exemplar = consumer_rows[0]
        payload_without_ref = {
            "schema_version": SOURCE_DISCOVERY_DEMAND_SCHEMA_VERSION,
            "failed_fetch_ref": fetch_ref,
            "failed_fetch_receipt_ref": _text(receipt.get("receipt_ref")),
            "original_locator": original_url,
            "failure_status": _text(receipt.get("status")),
            "failure_type": _text(receipt.get("failure_type")),
            "failure_detail": _text(receipt.get("failure_detail")),
            "consumer_residual_refs": consumer_refs,
            "subject_qids": sorted({_text(row.get("subject_qid")) for row in consumer_rows}),
            "statement_references": sorted({_text(row.get("statement_reference")) for row in consumer_rows}),
            "source_properties": sorted({_text(row.get("source_property")) for row in consumer_rows}),
            "target_properties": sorted({_text(row.get("target_property")) for row in consumer_rows}),
            "persistent_identifier_hints": _persistent_identifier_hints(original_url),
            "query_seeds": _query_seeds(
                original_url=original_url,
                subject_qid=_text(exemplar.get("subject_qid")),
                statement_reference=_text(exemplar.get("statement_reference")),
                source_property=_text(exemplar.get("source_property")),
                target_property=_text(exemplar.get("target_property")),
            ),
            "provider_neutral": True,
            "same_source_identity_required": True,
            "source_support_payment_claimed": False,
            "authority_evaluated": False,
            "semantic_promotion_authority": False,
        }
        payload = dict(payload_without_ref)
        payload["demand_ref"] = "nat-source-discovery-demand:" + canonical_sha256(payload_without_ref)
        demands.append(payload)

    demands.sort(key=lambda item: item["demand_ref"])
    payload_without_ref = {
        "schema_version": SOURCE_DISCOVERY_PLAN_SCHEMA_VERSION,
        "source_fetch_plan_ref": _text(source_plan.get("plan_ref")),
        "source_fetch_dispatch_ref": _text(source_dispatch.get("dispatch_ref")),
        "failed_locator_count": len(demands),
        "blocked_residual_count": len(
            {
                ref
                for demand in demands
                for ref in demand["consumer_residual_refs"]
            }
        ),
        "demands": demands,
        "source_support_paid_count": 0,
        "same_source_identity_paid_count": 0,
        "authority_evaluated": False,
        "semantic_promotion_performed": False,
    }
    payload = dict(payload_without_ref)
    payload["plan_ref"] = "nat-source-discovery-plan:" + canonical_sha256(payload_without_ref)
    return payload


class SourceDiscoveryProvider(Protocol):
    def __call__(self, demand: Mapping[str, Any]) -> Mapping[str, Any]: ...


def normalize_discovery_provider_receipt(
    demand: Mapping[str, Any],
    raw_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """Normalize Tavily/Google/Exa/MCP/human discovery output.

    Provider rank/snippet/title are scheduling metadata only. A normalized candidate
    is not a same-source identity receipt and cannot pay source support.
    """

    provider = _text(raw_receipt.get("provider")) or "unspecified"
    provider_call_ref = _text(raw_receipt.get("provider_call_ref"))
    candidates: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for index, item in enumerate(_sequence(raw_receipt.get("candidates"))):
        if not isinstance(item, Mapping):
            continue
        url = _text(item.get("url"))
        if not url or url in seen_urls:
            continue
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            continue
        seen_urls.add(url)
        payload_without_ref = {
            "schema_version": SOURCE_LOCATOR_CANDIDATE_SCHEMA_VERSION,
            "source_discovery_demand_ref": _text(demand.get("demand_ref")),
            "provider": provider,
            "provider_call_ref": provider_call_ref,
            "provider_result_ref": _text(item.get("provider_result_ref")),
            "candidate_locator": url,
            "title": _text(item.get("title")),
            "snippet": _text(item.get("snippet")),
            "rank": int(item.get("rank", index + 1) or index + 1),
            "same_source_identity_state": "open",
            "same_source_identity_trit": 0,
            "source_support_paid": False,
            "authority_evaluated": False,
        }
        payload = dict(payload_without_ref)
        payload["candidate_ref"] = "nat-source-locator-candidate:" + canonical_sha256(payload_without_ref)
        candidates.append(payload)
    candidates.sort(key=lambda item: (item["rank"], item["candidate_ref"]))

    payload_without_ref = {
        "schema_version": SOURCE_DISCOVERY_RECEIPT_SCHEMA_VERSION,
        "source_discovery_demand_ref": _text(demand.get("demand_ref")),
        "provider": provider,
        "provider_call_ref": provider_call_ref,
        "query_refs": [str(item) for item in _sequence(raw_receipt.get("query_refs"))],
        "candidate_count": len(candidates),
        "candidates": candidates,
        "same_source_identity_paid": False,
        "source_support_paid": False,
        "authority_evaluated": False,
        "semantic_promotion_performed": False,
    }
    payload = dict(payload_without_ref)
    payload["receipt_ref"] = "nat-source-discovery-receipt:" + canonical_sha256(payload_without_ref)
    return payload


def execute_source_discovery_plan(
    plan: Mapping[str, Any],
    provider: SourceDiscoveryProvider,
) -> dict[str, Any]:
    receipts: list[dict[str, Any]] = []
    for demand in _sequence(plan.get("demands")):
        if not isinstance(demand, Mapping):
            continue
        raw = provider(demand)
        if not isinstance(raw, Mapping):
            raise ValueError("source discovery provider must return a mapping")
        receipts.append(normalize_discovery_provider_receipt(demand, raw))
    receipts.sort(key=lambda item: item["receipt_ref"])
    payload_without_ref = {
        "source_discovery_plan_ref": _text(plan.get("plan_ref")),
        "receipt_count": len(receipts),
        "candidate_count": sum(int(item.get("candidate_count", 0) or 0) for item in receipts),
        "receipts": receipts,
        "same_source_identity_paid_count": 0,
        "source_support_paid_count": 0,
        "semantic_promotion_performed": False,
    }
    payload = dict(payload_without_ref)
    payload["dispatch_ref"] = "nat-source-discovery-dispatch:" + canonical_sha256(payload_without_ref)
    return payload


def build_same_source_identity_receipt(
    demand: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    disposition: str,
    verifier_reference: str,
    identity_evidence_locator: str,
    verification_note: str = "",
) -> dict[str, Any]:
    if _text(candidate.get("source_discovery_demand_ref")) != _text(demand.get("demand_ref")):
        raise ValueError("candidate is not bound to this discovery demand")
    if disposition not in {"same_source", "different_source", "unresolved"}:
        raise ValueError("invalid same-source identity disposition")
    if disposition in {"same_source", "different_source"} and not identity_evidence_locator.strip():
        raise ValueError("terminal source-identity disposition requires evidence locator")
    trit = 1 if disposition == "same_source" else -1 if disposition == "different_source" else 0
    state = "admitted" if trit == 1 else "rejected" if trit == -1 else "open"
    payload_without_ref = {
        "schema_version": SAME_SOURCE_IDENTITY_RECEIPT_SCHEMA_VERSION,
        "source_discovery_demand_ref": _text(demand.get("demand_ref")),
        "candidate_ref": _text(candidate.get("candidate_ref")),
        "original_locator": _text(demand.get("original_locator")),
        "candidate_locator": _text(candidate.get("candidate_locator")),
        "verifier_reference": verifier_reference,
        "identity_evidence_locator": identity_evidence_locator,
        "verification_note": verification_note,
        "disposition": disposition,
        "same_source_identity_state": state,
        "same_source_identity_trit": trit,
        "same_source_identity_paid": disposition == "same_source",
        "source_support_paid": False,
        "authority_evaluated": False,
        "semantic_promotion_performed": False,
    }
    payload = dict(payload_without_ref)
    payload["receipt_ref"] = "nat-same-source-identity-receipt:" + canonical_sha256(payload_without_ref)
    return payload


def build_alternate_source_fetch_plan(
    discovery_plan: Mapping[str, Any],
    discovery_dispatch: Mapping[str, Any],
    identity_receipts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    demands = {
        _text(item.get("demand_ref")): item
        for item in _sequence(discovery_plan.get("demands"))
        if isinstance(item, Mapping)
    }
    candidates = {
        _text(candidate.get("candidate_ref")): candidate
        for receipt in _sequence(discovery_dispatch.get("receipts"))
        if isinstance(receipt, Mapping)
        for candidate in _sequence(receipt.get("candidates"))
        if isinstance(candidate, Mapping)
    }
    locator_consumers: dict[str, set[str]] = defaultdict(set)
    accepted_identity_refs: list[str] = []
    for receipt in identity_receipts:
        if not isinstance(receipt, Mapping) or not bool(receipt.get("same_source_identity_paid")):
            continue
        candidate = candidates.get(_text(receipt.get("candidate_ref")))
        if not isinstance(candidate, Mapping):
            raise ValueError("identity receipt names unknown discovery candidate")
        demand_ref = _text(receipt.get("source_discovery_demand_ref"))
        demand = demands.get(demand_ref)
        if not isinstance(demand, Mapping):
            raise ValueError("identity receipt names unknown discovery demand")
        if _text(candidate.get("source_discovery_demand_ref")) != demand_ref:
            raise ValueError("identity receipt/candidate demand mismatch")
        locator = _text(candidate.get("candidate_locator"))
        for residual_ref in _sequence(demand.get("consumer_residual_refs")):
            if _text(residual_ref):
                locator_consumers[locator].add(_text(residual_ref))
        accepted_identity_refs.append(_text(receipt.get("receipt_ref")))

    fetch_demands: list[dict[str, Any]] = []
    for locator in sorted(locator_consumers):
        payload_without_ref = {
            "url": locator,
            "consumer_residual_refs": sorted(locator_consumers[locator]),
            "candidate_only": False,
            "alternate_locator_same_source_identity_admitted": True,
            "content_acquisition_only": True,
            "source_support_payment_claimed": False,
            "semantic_promotion_authority": False,
        }
        payload = dict(payload_without_ref)
        payload["fetch_ref"] = "nat-source-fetch-demand:" + canonical_sha256(payload_without_ref)
        fetch_demands.append(payload)

    payload_without_ref = {
        "schema_version": ALTERNATE_SOURCE_FETCH_PLAN_SCHEMA_VERSION,
        "source_discovery_plan_ref": _text(discovery_plan.get("plan_ref")),
        "source_discovery_dispatch_ref": _text(discovery_dispatch.get("dispatch_ref")),
        "accepted_identity_receipt_refs": sorted(set(accepted_identity_refs)),
        "distinct_url_count": len(fetch_demands),
        "fetch_demands": fetch_demands,
        "source_support_paid_count": 0,
        "authority_evaluated": False,
        "semantic_promotion_performed": False,
    }
    payload = dict(payload_without_ref)
    payload["plan_ref"] = "nat-alternate-source-fetch-plan:" + canonical_sha256(payload_without_ref)
    return payload


__all__ = [
    "ALTERNATE_SOURCE_FETCH_PLAN_SCHEMA_VERSION",
    "SAME_SOURCE_IDENTITY_RECEIPT_SCHEMA_VERSION",
    "SOURCE_DISCOVERY_DEMAND_SCHEMA_VERSION",
    "SOURCE_DISCOVERY_PLAN_SCHEMA_VERSION",
    "SOURCE_DISCOVERY_RECEIPT_SCHEMA_VERSION",
    "SOURCE_LOCATOR_CANDIDATE_SCHEMA_VERSION",
    "SourceDiscoveryProvider",
    "build_alternate_source_fetch_plan",
    "build_same_source_identity_receipt",
    "build_source_discovery_plan",
    "execute_source_discovery_plan",
    "normalize_discovery_provider_receipt",
]
