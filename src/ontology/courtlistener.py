from __future__ import annotations

import json
from typing import Any

from src.policy.compiler_contract import (
    build_compiler_contract_payload,
    DerivedProductContract,
    EvidenceBundleContract,
    PromotedOutcomeContract,
)
from src.policy.suite_normalized_artifact import SUITE_NORMALIZED_ARTIFACT_SCHEMA_VERSION
from src.sources.courtlistener import CourtListenerStatuteAdapter


def build_courtlistener_statute_case_follow(
    statute_id: str,
    *,
    limit: int = 3,
    adapter: CourtListenerStatuteAdapter | None = None,
) -> dict[str, Any]:
    adapter = adapter or CourtListenerStatuteAdapter()
    fetch_result = adapter.fetch(statute_id)
    payload = json.loads(fetch_result.content.decode("utf-8"))
    cases = payload.get("cases", [])[:limit]
    evidence_bundle = EvidenceBundleContract(
        bundle_kind="statute_case_follow",
        source_family="courtlistener_statutes",
        source_count=1,
        item_count=len(cases),
        item_label="case",
    )
    promoted_outcomes = PromotedOutcomeContract(
        outcome_family="case_law_follow_outcomes",
        promoted_count=0,
        review_count=len(cases),
        abstained_count=0,
        outcome_labels=("case_review",),
    )
    compiler_contract = build_compiler_contract_payload(
        lane="gwb",
        evidence_bundle=evidence_bundle,
        promoted_outcomes=promoted_outcomes,
        derived_products=(
            DerivedProductContract("packet", "courtlistener_statute_case_follow", True),
        ),
    )
    return {
        "schema_version": SUITE_NORMALIZED_ARTIFACT_SCHEMA_VERSION,
        "artifact_role": "derived_product",
        "artifact_id": f"courtlistener.statute_cases:{statute_id}",
        "canonical_identity": {
            "identity_class": "statute_case_follow",
            "identity_key": statute_id,
            "aliases": ["courtlistener_statute_case_follow"],
        },
        "provenance_anchor": {
            "source_system": "SensibLaw",
            "source_artifact_id": fetch_result.url,
            "anchor_kind": "statute_follow",
            "anchor_ref": "courtlistener.statute_cases",
        },
        "context_envelope_ref": {
            "envelope_id": f"courtlistener:{statute_id}",
            "envelope_kind": "courtlistener_statute_case_follow",
        },
        "authority": {
            "authority_class": "derived_inspection",
            "derived": True,
            "promotion_receipt_ref": None,
        },
        "lineage": {
            "upstream_artifact_ids": [statute_id],
            "profile_version": compiler_contract["schema_version"],
        },
        "compiler_contract": compiler_contract,
        "follow_obligation": {
            "trigger": statute_id,
            "scope": "bounded_case_law_follow",
            "stop_condition": "stop once the listed official case copies are confirmed or a new authoritative citation emerges",
        },
        "unresolved_pressure_status": "follow_needed",
        "summary": {
            "lane": "gwb",
            "statute_id": statute_id,
            "statute_title": payload.get("title") or "",
            "case_count": len(cases),
            "source_family": "courtlistener_statutes",
        },
        "cases": cases,
        "metadata": {
            "statute_url": payload.get("statute_url"),
            "description": payload.get("description"),
        },
    }


__all__ = ["build_courtlistener_statute_case_follow"]
