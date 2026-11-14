"""Source-preserving NORA candidate-review adapter (not a NORA API parser).

This is an internal, candidate-only handoff. A future pinned NORA export parser
must supply the source and review mappings. It does not grant Wikidata access,
semantic truth, SLR S29 review persistence, or Agda/Lean proof certification.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from src.policy.carriers.canonical import canonical_sha256, canonical_value, require_text


SCHEMA_VERSION = "sl.nora_review_handoff.v0_1"
CHOICE_KIND = {
    "valid": "review_judgement",
    "invalid": "review_judgement",
    "ambiguous": "unresolved_judgement",
    "manual_search": "acquisition_request",
    "modeling_gap": "model_residual",
}
CONSUMER_RESULTS = frozenset({"sufficient_claim", "non_descent_claim", "unresolved"})


def _mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a mapping")
    return canonical_value(value)


def _rows(value: Any, name: str) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{name} must be a list")
    return [_mapping(row, name) for row in value]


def _source_guard(source: Mapping[str, Any]) -> None:
    for key in ("candidate_ref", "source_field_ref", "source_revision_ref", "target_property_ref"):
        require_text(source.get(key), key)
    refs = _rows(source.get("attribution"), "attribution")
    if not refs:
        raise ValueError("attribution must retain at least one source record")
    for entry in refs:
        for key in ("actor_ref", "role", "source_ref"):
            require_text(entry.get(key), f"attribution.{key}")
    if source.get("classification") == "split_required":
        plan = _mapping(source.get("split_plan"), "split_plan")
        guids = plan.get("source_statement_guids")
        targets = plan.get("target_statement_bundles")
        if not isinstance(guids, list) or not guids or not all(isinstance(g, str) and g for g in guids):
            raise ValueError("split_required needs source statement GUIDs")
        if not isinstance(targets, list) or len(targets) < 2:
            raise ValueError("split_required needs two or more target bundles")
        for target in targets:
            _mapping(target, "target_statement_bundle")


def _review_guard(review: Mapping[str, Any]) -> str:
    for key in ("review_ref", "reviewer_ref", "standpoint_ref", "source_revision_ref"):
        require_text(review.get(key), f"review.{key}")
    choice = require_text(review.get("choice"), "review.choice")
    if choice not in CHOICE_KIND:
        raise ValueError(f"unknown NORA reviewer choice: {choice}")
    if choice in {"invalid", "ambiguous", "modeling_gap"}:
        refs = review.get("reason_refs")
        if not isinstance(refs, list) or not refs or not all(isinstance(r, str) and r for r in refs):
            raise ValueError(f"{choice} needs at least one reason or residual reference")
    return choice


def _checks_guard(checks: list[dict[str, Any]]) -> None:
    seen: set[str] = set()
    for row in checks:
        consumer = require_text(row.get("consumer_ref"), "consumer_ref")
        require_text(row.get("standpoint_ref"), "consumer.standpoint_ref")
        require_text(row.get("source_revision_ref"), "consumer.source_revision_ref")
        if consumer in seen:
            raise ValueError(f"duplicate consumer: {consumer}")
        seen.add(consumer)
        result = require_text(row.get("result"), "consumer.result")
        if result not in CONSUMER_RESULTS:
            raise ValueError(f"unknown consumer result: {result}")
        if result == "non_descent_claim":
            require_text(row.get("witness_ref"), "consumer.witness_ref")
        if result == "sufficient_claim":
            require_text(row.get("witness_ref"), "consumer.witness_ref")


def build_nora_review_handoff(
    *, source_candidate: Mapping[str, Any], review: Mapping[str, Any],
    consumer_checks: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Preserve the exact supplied carriers. Never pay truth or edit authority."""
    source = _mapping(source_candidate, "source_candidate")
    decision = _mapping(review, "review")
    checks = _rows(consumer_checks, "consumer_checks")
    _source_guard(source)
    choice = _review_guard(decision)
    if decision["source_revision_ref"] != source["source_revision_ref"]:
        raise ValueError("review/source revision mismatch")
    _checks_guard(checks)
    for row in checks:
        if row["source_revision_ref"] != source["source_revision_ref"]:
            raise ValueError("consumer/source revision mismatch")

    payload = {
        "schema_version": SCHEMA_VERSION,
        "source_candidate": source,
        "source_candidate_digest": canonical_sha256(source),
        "review": decision,
        "review_digest": canonical_sha256(decision),
        "choice_kind": CHOICE_KIND[choice],
        "consumer_checks": checks,
        "consumer_checks_digest": canonical_sha256(checks),
        "reported_consumer_results_not_kernel_proofs": True,
        "semantic_truth_paid": False,
        "global_mapping_validity_paid": False,
        "promotion_authority_paid": False,
        "external_edit_authority_paid": False,
        "slr_s29_persistence_performed": False,
        "nora_native_export_verified": False,
        "source_adjudication_performed": False,
    }
    payload["handoff_ref"] = "nora-review:" + canonical_sha256(payload)
    return payload


def replay_nora_review_handoff(handoff: Mapping[str, Any]) -> dict[str, Any]:
    """Fail closed on altered source, review, consumer checks, or receipt digest."""
    record = _mapping(handoff, "handoff")
    if record.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported NORA handoff version")
    original = build_nora_review_handoff(
        source_candidate=_mapping(record.get("source_candidate"), "source_candidate"),
        review=_mapping(record.get("review"), "review"),
        consumer_checks=_rows(record.get("consumer_checks"), "consumer_checks"),
    )
    if record != original:
        raise ValueError("NORA handoff replay mismatch")
    return original


def check_nora_revision(handoff: Mapping[str, Any], current_source_revision_ref: str) -> dict[str, Any]:
    """Return a review route. Do not claim to reopen SLR database records."""
    receipt = replay_nora_review_handoff(handoff)
    current = require_text(current_source_revision_ref, "current_source_revision_ref")
    pinned = receipt["source_candidate"]["source_revision_ref"]
    return {
        "handoff_ref": receipt["handoff_ref"],
        "pinned_source_revision_ref": pinned,
        "current_source_revision_ref": current,
        "review_recheck_required": current != pinned,
        "slr_reopening_performed": False,
    }


def nora_acquisition_route(handoff: Mapping[str, Any]) -> dict[str, Any]:
    """Plan a possible SLR/ITIR source job. Never dispatch a provider request."""
    receipt = replay_nora_review_handoff(handoff)
    decision = receipt["review"]
    return {
        "handoff_ref": receipt["handoff_ref"],
        "requested": decision["choice"] == "manual_search",
        "source_revision_ref": receipt["source_candidate"]["source_revision_ref"],
        "source_field_ref": receipt["source_candidate"]["source_field_ref"],
        "reason_refs": decision.get("reason_refs", []),
        "candidate_only": True,
        "provider_execution_performed": False,
    }
