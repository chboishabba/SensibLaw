from __future__ import annotations

from typing import Any, Mapping, Sequence


FOLLOW_DEPTH_SCHEMA_VERSION = "sl.wikidata_review_packet.follow_depth.v0_1"


def _as_text_list(values: Sequence[Any] | None) -> list[str]:
    if values is None:
        return []
    normalized: list[str] = []
    for value in values:
        text = str(value).strip()
        if text:
            normalized.append(text)
    return normalized


def _bounded_excerpt(text: str, *, max_excerpt_chars: int) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= max_excerpt_chars:
        return normalized
    clipped = normalized[: max_excerpt_chars - 1].rstrip()
    return f"{clipped}..."


def enrich_follow_receipt_with_depth(
    follow_receipt: Mapping[str, Any],
    *,
    source_text: str | None = None,
    max_excerpt_chars: int = 240,
) -> dict[str, Any]:
    """
    Build a bounded follow-depth view for one follow receipt.

    This is fail-closed: if no bounded excerpt can be produced, the result
    explicitly reports `no_excerpt_available` and does not fabricate evidence.
    """
    receipt_id = str(follow_receipt.get("receipt_id", "")).strip()
    url = str(follow_receipt.get("url", "")).strip()
    evidence = _as_text_list(follow_receipt.get("extracted_evidence"))
    unresolved = _as_text_list(follow_receipt.get("unresolved_uncertainty"))

    result: dict[str, Any] = {
        "receipt_id": receipt_id,
        "url": url,
        "unresolved_uncertainty": unresolved,
    }
    if evidence:
        result["status"] = "enriched"
        result["excerpt_source"] = "extracted_evidence"
        result["evidence_excerpt"] = _bounded_excerpt(
            evidence[0],
            max_excerpt_chars=max_excerpt_chars,
        )
        if len(evidence) > 1:
            result["evidence_summary"] = "; ".join(evidence[:2])
        return result

    source_text_normalized = (source_text or "").strip()
    if source_text_normalized:
        result["status"] = "enriched"
        result["excerpt_source"] = "source_text"
        result["evidence_excerpt"] = _bounded_excerpt(
            source_text_normalized,
            max_excerpt_chars=max_excerpt_chars,
        )
        result["evidence_summary"] = "derived_from_bounded_source_text"
        result["unresolved_uncertainty"] = sorted(
            set(unresolved + ["excerpt_derived_without_explicit_extracted_evidence"])
        )
        return result

    result["status"] = "no_excerpt_available"
    result["failure_reason"] = "no_extracted_evidence_or_source_text"
    return result


def enrich_review_packet_follow_depth(
    review_packet: Mapping[str, Any],
    *,
    source_text_by_url: Mapping[str, str] | None = None,
    max_excerpt_chars: int = 240,
) -> dict[str, Any]:
    source_lookup = source_text_by_url or {}
    follow_receipts = review_packet.get("follow_receipts")
    if not isinstance(follow_receipts, Sequence):
        follow_receipts = []

    enriched_receipts: list[dict[str, Any]] = []
    for raw_receipt in follow_receipts:
        if not isinstance(raw_receipt, Mapping):
            continue
        url = str(raw_receipt.get("url", "")).strip()
        source_text = source_lookup.get(url)
        enriched_receipts.append(
            enrich_follow_receipt_with_depth(
                raw_receipt,
                source_text=source_text,
                max_excerpt_chars=max_excerpt_chars,
            )
        )

    enriched_count = sum(1 for receipt in enriched_receipts if receipt.get("status") == "enriched")
    no_excerpt_count = sum(
        1 for receipt in enriched_receipts if receipt.get("status") == "no_excerpt_available"
    )
    return {
        "schema_version": FOLLOW_DEPTH_SCHEMA_VERSION,
        "packet_id": str(review_packet.get("packet_id", "")).strip(),
        "receipt_count": len(enriched_receipts),
        "enriched_count": enriched_count,
        "no_excerpt_count": no_excerpt_count,
        "receipts": enriched_receipts,
    }

