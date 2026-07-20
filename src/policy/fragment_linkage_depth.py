from __future__ import annotations

from typing import Any

from src.policy.fragment_pnf import (
    FragmentPNFDepthReceipt,
    LinkageDepthLevel,
)


def _find_source_span(row: dict[str, Any]) -> bool:
    anchor = row.get("anchor") or {}
    return bool(
        row.get("source_path")
        or row.get("source_url")
        or row.get("citation_refs")
        or anchor.get("text")
        or anchor.get("year")
    )


def _find_token_span(row: dict[str, Any]) -> bool:
    return bool(
        row.get("mentions")
        or any(
            isinstance(ref, dict) and "span" in ref
            for ref in (row.get("citation_refs") or [])
        )
    )


def _find_fragment_pnf(row: dict[str, Any]) -> bool:
    return bool(row.get("fragment_pnfs"))


def _find_sentence_pnf(row: dict[str, Any]) -> bool:
    return bool(row.get("projected_predicate_atoms"))


def _find_document_pnf(row: dict[str, Any]) -> bool:
    return bool(
        row.get("doc_title")
        and len(row.get("text", "")) > 200
    )


def _find_braid_attachment(row: dict[str, Any]) -> bool:
    return bool(
        row.get("braid_metrics")
        and row["braid_metrics"].get("connectedness", 0) > 0
    )


def assess_linkage_depth(row: dict[str, Any]) -> FragmentPNFDepthReceipt:
    has_source_span = _find_source_span(row)
    has_token_span = _find_token_span(row)
    has_fragment_pnf = _find_fragment_pnf(row)
    has_sentence_pnf = _find_sentence_pnf(row)
    has_document_pnf = _find_document_pnf(row)
    has_braid_attachment = _find_braid_attachment(row)

    return FragmentPNFDepthReceipt.from_atom(
        row,
        has_source_span=has_source_span,
        has_token_span=has_token_span,
        has_fragment_pnf=has_fragment_pnf,
        has_sentence_pnf=has_sentence_pnf,
        has_document_pnf=has_document_pnf,
        has_braid_attachment=has_braid_attachment,
    )


def classify_linkage_depth_level(receipt: FragmentPNFDepthReceipt) -> LinkageDepthLevel:
    if receipt.braid_attachment_present:
        return LinkageDepthLevel.braid_node
    if receipt.document_pnf_present:
        return LinkageDepthLevel.document_pnf
    if receipt.sentence_pnf_present:
        return LinkageDepthLevel.sentence_pnf
    if receipt.fragment_pnf_present:
        return LinkageDepthLevel.fragment_pnf
    if receipt.source_span_present:
        return LinkageDepthLevel.source_span
    return LinkageDepthLevel.flat_shortcut


def assess_and_store_linkage_depth(row: dict[str, Any]) -> None:
    receipt = assess_linkage_depth(row)
    row["linkage_depth_receipt"] = receipt.to_dict()
    row["linkage_depth_level"] = classify_linkage_depth_level(receipt).value
    row["flat_shortcut_detected"] = receipt.flat_shortcut_detected


def assess_rows_linkage_depth(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for row in rows:
        assess_and_store_linkage_depth(row)
    return rows


__all__ = [
    "assess_and_store_linkage_depth",
    "assess_linkage_depth",
    "assess_rows_linkage_depth",
    "classify_linkage_depth_level",
]
