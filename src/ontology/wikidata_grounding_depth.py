from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

GROUNDING_DEPTH_SCHEMA_VERSION = "sl.wikidata_review_packet.grounding_depth.v0_1"
GROUNDING_ATTACHMENT_SCHEMA_VERSION = "sl.wikidata_review_packet.grounding_depth_attachment.v0_1"
GROUNDING_BATCH_SCHEMA_VERSION = "sl.wikidata_review_packet.grounding_depth_batch.v0_1"
GROUNDING_EVIDENCE_REPORT_SCHEMA_VERSION = (
    "sl.wikidata_review_packet.grounding_depth_evidence_report.v0_1"
)
GROUNDING_SCORECARD_SCHEMA_VERSION = (
    "sl.wikidata_review_packet.grounding_depth_scorecard.v0_1"
)
GROUNDING_ATTACHMENT_SCHEMA_VERSION = "sl.wikidata_review_packet.grounding_depth_attachment.v0_1"


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_revision_evidence(entry: Mapping[str, Any]) -> dict[str, Any]:
    excerpt = _normalize_text(entry.get("excerpt"))
    summary = _normalize_text(entry.get("excerpt_summary"))
    url = _normalize_text(entry.get("follow_receipt_url"))
    result = {
        "follow_receipt_url": url,
        "excerpt": excerpt,
        "excerpt_summary": summary,
    }
    missing: list[str] = []
    if not excerpt:
        missing.append("excerpt")
    if not summary:
        missing.append("excerpt_summary")
    if missing:
        result["status"] = "incomplete"
        result["missing_fields"] = missing
    else:
        result["status"] = "ok"
    return result


def _iter_packets(payload: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    for packet in payload.get("sample_packets") or []:
        if isinstance(packet, Mapping):
            yield packet


def build_grounding_depth_summary(
    *,
    fixture: Mapping[str, Any],
    max_packets: int | None = None,
) -> dict[str, Any]:
    packets: list[dict[str, Any]] = []
    for index, sample in enumerate(_iter_packets(fixture)):
        if max_packets is not None and index >= max_packets:
            break
        evidence = []
        for entry in sample.get("revision_evidence") or []:
            if not isinstance(entry, Mapping):
                continue
            evidence.append(_normalize_revision_evidence(entry))
        status = "missing_evidence"
        if evidence and all(item.get("status") == "ok" for item in evidence):
            status = "grounded"
        packets.append(
            {
                "packet_id": _normalize_text(sample.get("packet_id")),
                "qid": _normalize_text(sample.get("qid")),
                "revision_url": _normalize_text(sample.get("revision_url")),
                "revision_locked_notes": _normalize_text(sample.get("revision_locked_notes")),
                "grounding_status": status,
                "revision_evidence": evidence,
            }
        )
    grounded = sum(1 for packet in packets if packet["grounding_status"] == "grounded")
    return {
        "schema_version": GROUNDING_DEPTH_SCHEMA_VERSION,
        "lane_id": _normalize_text(fixture.get("lane_id")),
        "grounding_status": "partial" if grounded < len(packets) else "complete",
        "packet_count": len(packets),
        "grounded_packet_count": grounded,
        "packets": packets,
    }


def build_grounding_depth_attachment(
    *,
    review_packet: Mapping[str, Any],
    grounding_summary: Mapping[str, Any],
) -> dict[str, Any]:
    packet_id = _normalize_text(review_packet.get("packet_id"))
    qid = _normalize_text(review_packet.get("review_entity_qid"))
    packets = grounding_summary.get("packets") or []
    matched: Mapping[str, Any] | None = None
    for entry in packets:
        if not isinstance(entry, Mapping):
            continue
        if entry.get("packet_id") == packet_id and entry.get("qid") == qid:
            matched = entry
            break
    if matched is None:
        return {
            "schema_version": GROUNDING_ATTACHMENT_SCHEMA_VERSION,
            "packet_id": packet_id,
            "qid": qid,
            "grounding_status": "no_grounding_data",
            "evidence": [],
            "notes": ["no grounding data matched the provided packet"],
        }
    return {
        "schema_version": GROUNDING_ATTACHMENT_SCHEMA_VERSION,
        "packet_id": packet_id,
        "qid": qid,
        "revision_url": matched.get("revision_url"),
        "grounding_status": matched.get("grounding_status"),
        "evidence": matched.get("revision_evidence"),
        "notes": [matched.get("revision_locked_notes", "")],
    }


def build_grounding_depth_batch(
    *,
    review_packets: Sequence[Mapping[str, Any]],
    grounding_summary: Mapping[str, Any],
) -> dict[str, Any]:
    attachments: list[dict[str, Any]] = []
    for packet in review_packets:
        if not isinstance(packet, Mapping):
            continue
        attachments.append(
            build_grounding_depth_attachment(
                review_packet=packet,
                grounding_summary=grounding_summary,
            )
        )
    return {
        "schema_version": GROUNDING_BATCH_SCHEMA_VERSION,
        "lane_id": _normalize_text(grounding_summary.get("lane_id")),
        "attachment_count": len(attachments),
        "attachments": attachments,
    }


def build_grounding_depth_evidence_report(
    *, grounding_summary: Mapping[str, Any]
) -> dict[str, Any]:
    packets: list[dict[str, Any]] = []
    grounded = 0
    for entry in grounding_summary.get("packets") or []:
        if not isinstance(entry, Mapping):
            continue
        evidence = entry.get("revision_evidence") or []
        missing_fields = []
        for item in evidence:
            if isinstance(item, Mapping):
                missing_fields.extend(item.get("missing_fields", []))
        packet_record = {
            "packet_id": _normalize_text(entry.get("packet_id")),
            "qid": _normalize_text(entry.get("qid")),
            "revision_url": _normalize_text(entry.get("revision_url")),
            "grounding_status": entry.get("grounding_status"),
            "evidence_count": len(evidence),
            "missing_fields": sorted(set(missing_fields)),
            "notes": [entry.get("revision_locked_notes")] if entry.get("revision_locked_notes") else [],
        }
        packets.append(packet_record)
        if entry.get("grounding_status") == "grounded":
            grounded += 1
    return {
        "schema_version": GROUNDING_EVIDENCE_REPORT_SCHEMA_VERSION,
        "lane_id": _normalize_text(grounding_summary.get("lane_id")),
        "packet_count": len(packets),
        "grounded_packet_count": grounded,
        "packets": packets,
    }


def build_grounding_depth_comparison(
    *, batches: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    comparison: list[dict[str, Any]] = []
    for index, batch in enumerate(batches):
        attachments = batch.get("attachments") or []
        status_counts: dict[str, int] = {}
        qids: list[str] = []
        for attachment in attachments:
            status = str(attachment.get("grounding_status") or "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
            qid = attachment.get("qid")
            if isinstance(qid, str) and qid:
                qids.append(qid)
        comparison.append(
            {
                "index": index,
                "lane_id": _normalize_text(batch.get("lane_id")),
                "attachment_count": len(attachments),
                "grounded_packet_count": status_counts.get("grounded", 0),
                "qids": qids,
                "status_counts": status_counts,
            }
        )
    return {
        "schema_version": GROUNDING_EVIDENCE_REPORT_SCHEMA_VERSION,
        "comparison_count": len(comparison),
        "comparison": comparison,
    }


def build_grounding_depth_scorecard(*, runs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    total_grounded = 0
    total_attachments = 0
    for run in runs:
        run_id = _normalize_text(run.get("run_id"))
        raw_comparison = run.get("comparison")
        if isinstance(raw_comparison, Mapping) and "comparison" in raw_comparison:
            comparison_list = raw_comparison.get("comparison", [])
        elif isinstance(raw_comparison, Sequence):
            comparison_list = raw_comparison or []
        else:
            comparison_list = []
        run_grounded = sum(
            int(entry.get("grounded_packet_count") or 0) for entry in comparison_list
        )
        run_attachments = sum(int(entry.get("attachment_count") or 0) for entry in comparison_list)
        total_grounded += run_grounded
        total_attachments += run_attachments
        run_status_counts: dict[str, int] = {}
        for entry in comparison_list:
            for status, count in (entry.get("status_counts") or {}).items():
                run_status_counts[str(status)] = (
                    run_status_counts.get(str(status), 0) + int(count or 0)
                )
        entries.append(
            {
                "run_id": run_id,
                "comparison_count": len(comparison_list),
                "grounded_packet_count": run_grounded,
                "attachment_count": run_attachments,
                "status_counts": run_status_counts,
            }
        )
    return {
        "schema_version": GROUNDING_SCORECARD_SCHEMA_VERSION,
        "run_count": len(entries),
        "total_grounded_packet_count": total_grounded,
        "total_attachment_count": total_attachments,
        "runs": entries,
    }
