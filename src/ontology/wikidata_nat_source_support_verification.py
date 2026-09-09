from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from src.policy.carriers.canonical import canonical_sha256


SOURCE_VERIFICATION_PLAN_SCHEMA_VERSION = "sl.nat_source_verification_plan.v0_1"
SOURCE_VERIFICATION_DEMAND_SCHEMA_VERSION = "sl.nat_source_verification_demand.v0_1"
SOURCE_VERIFICATION_RECEIPT_SCHEMA_VERSION = "sl.nat_source_verification_receipt.v0_1"
SOURCE_SUPPORT_ADMISSION_SCHEMA_VERSION = "sl.nat_source_support_admission.v0_1"


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


def _rows_by_ref(batch: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        _text(row.get("row_ref")): row
        for row in _sequence(batch.get("rows"))
        if isinstance(row, Mapping) and _text(row.get("row_ref"))
    }


def _candidates_by_digest(
    migration_packs: Sequence[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for pack in migration_packs:
        for candidate in _sequence(pack.get("candidates")):
            if isinstance(candidate, Mapping):
                result[canonical_sha256(candidate)] = candidate
    return result


def _receipts_by_url(source_dispatch: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        _text(receipt.get("url")): receipt
        for receipt in _sequence(source_dispatch.get("fetch_receipts"))
        if isinstance(receipt, Mapping) and _text(receipt.get("url"))
    }


def build_source_verification_plan(
    *,
    batch: Mapping[str, Any],
    source_plan: Mapping[str, Any],
    source_dispatch: Mapping[str, Any],
    migration_packs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Bind fetched source artifacts to the exact migration proposition per row.

    The exact proposition comes from the original migration-pack candidate selected
    by the dry row's content digest. The source verifier is not allowed to reconstruct
    a proposition from labels, QIDs, URL text, or candidate ordering.
    """

    rows = _rows_by_ref(batch)
    candidates = _candidates_by_digest(migration_packs)
    receipts = _receipts_by_url(source_dispatch)
    demands: list[dict[str, Any]] = []

    for residual in _sequence(source_plan.get("source_residuals")):
        if not isinstance(residual, Mapping):
            continue
        row_ref = _text(residual.get("source_row_ref"))
        row = rows.get(row_ref)
        if row is None:
            raise ValueError(f"source residual references unknown dry row: {row_ref}")
        candidate_digest = _text(row.get("input_digest"))
        candidate = candidates.get(candidate_digest)
        if candidate is None:
            state = "blocked_missing_exact_migration_candidate"
            before: Mapping[str, Any] = {}
            after: Mapping[str, Any] = {}
        else:
            before = _mapping(candidate.get("claim_bundle_before"))
            after = _mapping(candidate.get("claim_bundle_after"))
            expected_statement = _text(row.get("statement_reference"))
            observed_statement = _text(before.get("statement_id"))
            # Older migration-pack fixtures may omit statement_id inside the bundle.
            # In that case the dry row's input_digest is the same-object authority;
            # candidate_id is a row label and must not be substituted for a GUID.
            if (
                expected_statement
                and observed_statement
                and expected_statement != observed_statement
            ):
                raise ValueError(
                    f"migration candidate statement mismatch: {expected_statement} != {observed_statement}"
                )
            state = "ready"

        source_urls = [
            _text(url)
            for url in _sequence(residual.get("reference_urls"))
            if _text(url)
        ]
        acquired = [
            receipts[url]
            for url in source_urls
            if url in receipts and bool(receipts[url].get("content_acquired"))
        ]
        if state == "ready" and not acquired:
            state = "blocked_no_acquired_source_content"

        proposition = {
            "source_claim_bundle": dict(before),
            "target_claim_bundle": dict(after),
            "source_claim_digest": (
                "sha256:" + canonical_sha256(before) if before else ""
            ),
            "target_claim_digest": (
                "sha256:" + canonical_sha256(after) if after else ""
            ),
            "transformation_contract": "transform:P5991-to-P14143:preserve-statement-bundle",
            "verification_question": (
                "Does the source artifact support the exact quantity and preserved "
                "period/scope/method statement bundle represented by this row?"
            ),
        }
        payload_without_ref = {
            "schema_version": SOURCE_VERIFICATION_DEMAND_SCHEMA_VERSION,
            "source_residual_ref": _text(residual.get("residual_ref")),
            "source_row_ref": row_ref,
            "subject_qid": _text(residual.get("subject_qid")),
            "statement_reference": _text(residual.get("statement_reference")),
            "candidate_digest": candidate_digest,
            "state": state,
            "proposition": proposition,
            "source_artifacts": [
                {
                    "url": _text(receipt.get("url")),
                    "final_url": _text(receipt.get("final_url")),
                    "content_digest": _text(receipt.get("content_digest")),
                    "receipt_ref": _text(receipt.get("receipt_ref")),
                    "content_type": _text(receipt.get("content_type")),
                }
                for receipt in acquired
            ],
            "allowed_dispositions": ["supported", "contradicted", "unresolved"],
            "requires_evidence_locator": True,
            "source_support_payment_claimed": False,
            "authority_evaluated": False,
            "semantic_promotion_authority": False,
        }
        payload = dict(payload_without_ref)
        payload["demand_ref"] = "nat-source-verification-demand:" + canonical_sha256(
            payload_without_ref
        )
        demands.append(payload)

    demands.sort(key=lambda item: _text(item.get("demand_ref")))
    payload_without_ref = {
        "schema_version": SOURCE_VERIFICATION_PLAN_SCHEMA_VERSION,
        "source_batch_ref": _text(batch.get("batch_ref")),
        "source_fetch_plan_ref": _text(source_plan.get("plan_ref")),
        "source_fetch_dispatch_ref": _text(source_dispatch.get("dispatch_ref")),
        "demand_count": len(demands),
        "ready_count": sum(1 for demand in demands if demand["state"] == "ready"),
        "blocked_count": sum(1 for demand in demands if demand["state"] != "ready"),
        "demands": demands,
        "source_support_paid_count": 0,
        "authority_evaluated": False,
        "semantic_promotion_performed": False,
    }
    payload = dict(payload_without_ref)
    payload["plan_ref"] = "nat-source-verification-plan:" + canonical_sha256(
        payload_without_ref
    )
    return payload


def build_source_verification_receipt(
    demand: Mapping[str, Any],
    *,
    disposition: str,
    verifier_reference: str,
    source_artifact_receipt_ref: str,
    evidence_locator: str,
    verification_note: str = "",
) -> dict[str, Any]:
    if _text(demand.get("state")) != "ready":
        raise ValueError("source verification receipt requires a ready demand")
    if disposition not in {"supported", "contradicted", "unresolved"}:
        raise ValueError("invalid source proposition disposition")
    artifact_refs = {
        _text(item.get("receipt_ref"))
        for item in _sequence(demand.get("source_artifacts"))
        if isinstance(item, Mapping)
    }
    if source_artifact_receipt_ref not in artifact_refs:
        raise ValueError(
            "verification receipt must name an acquired artifact from the demand"
        )
    if disposition in {"supported", "contradicted"} and not evidence_locator.strip():
        raise ValueError("terminal source disposition requires an evidence locator")

    proposition = _mapping(demand.get("proposition"))
    payload_without_ref = {
        "schema_version": SOURCE_VERIFICATION_RECEIPT_SCHEMA_VERSION,
        "source_verification_demand_ref": _text(demand.get("demand_ref")),
        "source_residual_ref": _text(demand.get("source_residual_ref")),
        "source_row_ref": _text(demand.get("source_row_ref")),
        "candidate_digest": _text(demand.get("candidate_digest")),
        "source_claim_digest": _text(proposition.get("source_claim_digest")),
        "target_claim_digest": _text(proposition.get("target_claim_digest")),
        "source_artifact_receipt_ref": source_artifact_receipt_ref,
        "verifier_reference": verifier_reference,
        "evidence_locator": evidence_locator,
        "disposition": disposition,
        "verification_note": verification_note,
        "authority_evaluated": False,
        "semantic_promotion_performed": False,
    }
    payload = dict(payload_without_ref)
    payload["receipt_ref"] = "nat-source-verification-receipt:" + canonical_sha256(
        payload_without_ref
    )
    return payload


def admit_source_support(
    demand: Mapping[str, Any], verification: Mapping[str, Any]
) -> dict[str, Any]:
    if _text(verification.get("source_verification_demand_ref")) != _text(
        demand.get("demand_ref")
    ):
        raise ValueError("source verification receipt is not bound to this exact demand")
    proposition = _mapping(demand.get("proposition"))
    if _text(verification.get("source_claim_digest")) != _text(
        proposition.get("source_claim_digest")
    ):
        raise ValueError("source verification receipt changed the source proposition")
    if _text(verification.get("target_claim_digest")) != _text(
        proposition.get("target_claim_digest")
    ):
        raise ValueError("source verification receipt changed the target proposition")

    disposition = _text(verification.get("disposition"))
    paid = disposition == "supported"
    rejected = disposition == "contradicted"
    state = "admitted" if paid else "rejected" if rejected else "open"
    payload_without_ref = {
        "schema_version": SOURCE_SUPPORT_ADMISSION_SCHEMA_VERSION,
        "source_verification_demand_ref": _text(demand.get("demand_ref")),
        "source_verification_receipt_ref": _text(verification.get("receipt_ref")),
        "source_residual_ref": _text(demand.get("source_residual_ref")),
        "source_support_state": state,
        "source_support_trit": 1 if paid else -1 if rejected else 0,
        "source_support_paid": paid,
        "source_support_rejected": rejected,
        "authority_evaluated": False,
        "authority_state": "open",
        "semantic_promotion_performed": False,
        "migration_authority": False,
    }
    payload = dict(payload_without_ref)
    payload["admission_ref"] = "nat-source-support-admission:" + canonical_sha256(
        payload_without_ref
    )
    return payload


__all__ = [
    "SOURCE_SUPPORT_ADMISSION_SCHEMA_VERSION",
    "SOURCE_VERIFICATION_DEMAND_SCHEMA_VERSION",
    "SOURCE_VERIFICATION_PLAN_SCHEMA_VERSION",
    "SOURCE_VERIFICATION_RECEIPT_SCHEMA_VERSION",
    "admit_source_support",
    "build_source_verification_plan",
    "build_source_verification_receipt",
]
