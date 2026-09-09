from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from src.ontology.wikidata_nat_source_support import (
    fetch_source_content,
    recompute_source_support_observation,
)
from src.policy.carriers.canonical import canonical_sha256
from src.sources.rate_limit import RateLimit, TokenBucketRateLimiter


SOURCE_FETCH_DISPATCH_SCHEMA_VERSION = "sl.nat_source_fetch_dispatch.v0_1"


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _sequence(value: Any) -> Sequence[Any]:
    return (
        value
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))
        else ()
    )


def dispatch_source_fetch_plan(
    plan: Mapping[str, Any],
    *,
    fetcher: Callable[[Mapping[str, Any]], Mapping[str, Any]] = fetch_source_content,
    worker_budget: int = 4,
    max_fetches: int = 128,
    rate_limiter: Any | None = None,
) -> dict[str, Any]:
    """Execute each distinct external URL once and project back to source residuals.

    Physical source fetching is shared by URL. Semantic payment is never shared:
    each row receives its own source-support observation, and content acquisition
    alone is insufficient to pay source support.
    """

    demands = [
        dict(item)
        for item in _sequence(plan.get("fetch_demands"))
        if isinstance(item, Mapping)
    ]
    residuals = [
        dict(item)
        for item in _sequence(plan.get("source_residuals"))
        if isinstance(item, Mapping)
    ]
    demands.sort(key=lambda item: _text(item.get("fetch_ref")))
    residuals.sort(key=lambda item: _text(item.get("residual_ref")))
    if len(demands) > max_fetches:
        raise ValueError(
            f"source fetch plan contains {len(demands)} demands; max_fetches={max_fetches}"
        )

    workers = max(1, min(int(worker_budget), max(1, len(demands))))
    limiter = rate_limiter or TokenBucketRateLimiter(RateLimit(rps=1.0, burst=1))

    def run(demand: Mapping[str, Any]) -> dict[str, Any]:
        limiter.acquire()
        receipt = fetcher(demand)
        if not isinstance(receipt, Mapping):
            raise ValueError("source fetcher must return a mapping receipt")
        return dict(receipt)

    if demands:
        with ThreadPoolExecutor(
            max_workers=workers, thread_name_prefix="sensiblaw-nat-source"
        ) as pool:
            receipts = list(pool.map(run, demands))
    else:
        receipts = []

    receipts.sort(key=lambda item: _text(item.get("receipt_ref")))
    receipts_by_url = {
        _text(receipt.get("url")): receipt
        for receipt in receipts
        if _text(receipt.get("url"))
    }
    recomputations = [
        recompute_source_support_observation(residual, receipts_by_url)
        for residual in residuals
    ]
    recomputations.sort(key=lambda item: _text(item.get("recomputation_ref")))

    status_counts = Counter(_text(receipt.get("status")) for receipt in receipts)
    payload_without_ref = {
        "schema_version": SOURCE_FETCH_DISPATCH_SCHEMA_VERSION,
        "source_plan_ref": _text(plan.get("plan_ref")),
        "source_batch_ref": _text(plan.get("source_batch_ref")),
        "source_coverage_dispatch_ref": _text(plan.get("source_coverage_dispatch_ref")),
        "source_residual_count": len(residuals),
        "distinct_url_count": len(demands),
        "fetch_call_count": len(receipts),
        "worker_budget": workers,
        "rate_limit_policy": {
            "shared_across_workers": True,
            "rps": getattr(getattr(limiter, "cfg", None), "rps", None),
            "burst": getattr(getattr(limiter, "cfg", None), "burst", None),
        },
        "fetch_receipts": receipts,
        "counts_by_fetch_status": dict(sorted(status_counts.items())),
        "source_support_recomputations": recomputations,
        "source_support_recomputation_count": len(recomputations),
        "reference_present_count": sum(
            1 for item in recomputations if bool(item.get("reference_presence"))
        ),
        "content_acquired_residual_count": sum(
            1 for item in recomputations if bool(item.get("content_acquired"))
        ),
        "source_support_paid_count": 0,
        "source_support_still_open_count": len(recomputations),
        "network_performed": any(
            bool(receipt.get("network_performed")) for receipt in receipts
        ),
        "bytes_received": sum(int(receipt.get("bytes_received", 0) or 0) for receipt in receipts),
        "http_request_count": sum(
            int(receipt.get("http_request_count", 0) or 0) for receipt in receipts
        ),
        "cache_hits": sum(int(receipt.get("cache_hits", 0) or 0) for receipt in receipts),
        "cache_misses": sum(int(receipt.get("cache_misses", 0) or 0) for receipt in receipts),
        "consumer_verification_performed": False,
        "semantic_promotion_performed": False,
        "edits_performed": False,
    }
    payload = dict(payload_without_ref)
    payload["dispatch_ref"] = "nat-source-fetch-dispatch:" + canonical_sha256(
        payload_without_ref
    )
    return payload


__all__ = ["SOURCE_FETCH_DISPATCH_SCHEMA_VERSION", "dispatch_source_fetch_plan"]
