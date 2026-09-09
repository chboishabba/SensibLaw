from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from src.ontology.wikidata_nat_source_discovery import build_alternate_source_fetch_plan
from src.policy.carriers.canonical import canonical_sha256


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _sequence(value: Any) -> Sequence[Any]:
    return (
        value
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))
        else ()
    )


def build_replayable_alternate_source_fetch_plan(
    source_plan: Mapping[str, Any],
    discovery_plan: Mapping[str, Any],
    discovery_dispatch: Mapping[str, Any],
    identity_receipts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Compile admitted alternate locators onto the existing source-fetch contract.

    Only residuals consumed by an admitted same-source locator are copied into the
    replay plan. This keeps the existing URL-deduplicated dispatcher and residual-local
    recomputation path as the single transport implementation.
    """

    alternate = build_alternate_source_fetch_plan(
        discovery_plan,
        discovery_dispatch,
        identity_receipts,
    )
    consumer_refs = {
        _text(ref)
        for demand in _sequence(alternate.get("fetch_demands"))
        if isinstance(demand, Mapping)
        for ref in _sequence(demand.get("consumer_residual_refs"))
        if _text(ref)
    }
    source_residuals = [
        dict(item)
        for item in _sequence(source_plan.get("source_residuals"))
        if isinstance(item, Mapping) and _text(item.get("residual_ref")) in consumer_refs
    ]
    source_residuals.sort(key=lambda item: _text(item.get("residual_ref")))

    payload_without_ref = {
        **{key: value for key, value in alternate.items() if key != "plan_ref"},
        "source_batch_ref": _text(source_plan.get("source_batch_ref")),
        "source_coverage_dispatch_ref": _text(source_plan.get("source_coverage_dispatch_ref")),
        "source_residual_count": len(source_residuals),
        "source_residuals": source_residuals,
        "network_performed": False,
        "consumer_verification_performed": False,
        "edits_performed": False,
    }
    payload = dict(payload_without_ref)
    payload["plan_ref"] = "nat-alternate-source-fetch-plan:" + canonical_sha256(payload_without_ref)
    return payload


__all__ = ["build_replayable_alternate_source_fetch_plan"]
