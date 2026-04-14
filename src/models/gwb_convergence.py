from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.models.convergence import build_convergence_record


def _extract_receipt_sources(slice_payload: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    for row in slice_payload.get("source_review_rows", []) or []:
        if not isinstance(row, Mapping):
            continue
        seed_id = str(row.get("seed_id") or "")
        receipt_items: list[Mapping[str, Any]] = row.get("receipts", []) if isinstance(row.get("receipts"), list) else []
        for receipt in receipt_items:
            if not isinstance(receipt, Mapping):
                continue
            value = str(receipt.get("value") or receipt.get("link") or "").strip()
            rows.append(
                {
                    "source_unit_id": f"gwb_public:{seed_id}:{row.get('event_id') or 'event'}",
                    "root_artifact_id": value or f"trace:{seed_id}",
                    "source_family": "gwb_public_review",
                    "authority_level": "public",
                    "verification_status": "matched" if row.get("matched") else "unmatched",
                    "provenance_chain": {
                        "seed_id": seed_id,
                        "event_id": row.get("event_id"),
                        "receipts": [value] if value else [],
                    },
                }
            )
    return rows


def build_gwb_public_convergence(slice_payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(slice_payload, Mapping):
        raise ValueError("slice payload must be a mapping")
    claims = []
    for row in slice_payload.get("review_item_rows", []) or []:
        if not isinstance(row, Mapping):
            continue
        seed_id = str(row.get("seed_id") or row.get("review_item_id") or "")
        if not seed_id:
            continue
        claim_id = f"gwb-public:{seed_id}"
        claims.append(claim_id)
    evidence_paths = _extract_receipt_sources(slice_payload)
    claim_id = claims[0] if claims else "gwb-public:unknown"
    return build_convergence_record(
        claim_id=claim_id,
        evidence_paths=evidence_paths,
        independent_root_artifact_ids=[path["root_artifact_id"] for path in evidence_paths],
        claim_status="SINGLE_RUN" if evidence_paths else "RAW",
    )
