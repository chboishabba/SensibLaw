from __future__ import annotations

from datetime import datetime, timezone, timedelta
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
GROUNDING_PRIORITY_SURFACE_SCHEMA_VERSION = (
    "sl.wikidata_review_packet.grounding_depth_priority_surface.v0_1"
)
GROUNDING_ROUTING_SCHEMA_VERSION = "sl.wikidata_review_packet.grounding_depth_routing.v0_1"

HARD_GROUNDING_ALLOWED_SOURCE_CLASSES = ("named_revision_locked_source",)
HARD_GROUNDING_MAX_REVISION_AGE_DAYS = 365


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


def _normalize_live_follow_receipt(row: Mapping[str, Any]) -> dict[str, Any]:
    evidence = row.get("evidence")
    if not isinstance(evidence, Mapping):
        evidence = {}
    source_class = _normalize_text(row.get("chosen_source_class")) or _normalize_text(
        evidence.get("source_class")
    )
    reference_url = evidence.get("reference_url")
    revision_source = evidence.get("revision_source")
    title = ""
    original_url = ""
    if isinstance(reference_url, Mapping):
        title = _normalize_text(reference_url.get("title"))
        original_url = _normalize_text(reference_url.get("original_url"))
    elif isinstance(revision_source, Mapping):
        title = _normalize_text(revision_source.get("label"))
        original_url = _normalize_text(revision_source.get("revision_url"))
    revision_ts = ""
    revision = evidence.get("revision")
    if isinstance(revision, Mapping):
        revision_ts = _normalize_text(revision.get("revision_timestamp"))
    elif isinstance(revision_source, Mapping):
        revision_ts = _normalize_text(revision_source.get("revision_timestamp"))
    return {
        "plan_id": _normalize_text(row.get("plan_id")),
        "target_ref": _normalize_text(row.get("target_ref")),
        "uncertainty_kind": _normalize_text(row.get("uncertainty_kind")),
        "status": _normalize_text(row.get("status")) or "unknown",
        "source_class": source_class,
        "title": title,
        "source_url": original_url,
        "revision_timestamp": revision_ts,
    }


def _index_live_follow_results(
    live_follow_results: Sequence[Mapping[str, Any]] | None,
) -> dict[str, list[dict[str, Any]]]:
    receipts_by_qid: dict[str, list[dict[str, Any]]] = {}
    for payload in live_follow_results or []:
        if not isinstance(payload, Mapping):
            continue
        rows = payload.get("result_rows")
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            qid = _normalize_text(row.get("qid"))
            if not qid:
                continue
            receipts_by_qid.setdefault(qid, []).append(_normalize_live_follow_receipt(row))
    return receipts_by_qid


def _grounding_gap_class(*, grounding_status: str, evidence_count: int, missing_fields: Sequence[str]) -> str:
    if grounding_status == "grounded":
        return "grounded"
    if evidence_count <= 0:
        return "no_revision_evidence"
    missing = {str(value).strip() for value in missing_fields if str(value).strip()}
    if {"excerpt", "excerpt_summary"} <= missing:
        return "revision_evidence_missing"
    if missing:
        return "partial_revision_evidence"
    return "ungrounded_other"


def _recommended_follow_scope(*, gap_class: str) -> str:
    if gap_class == "grounded":
        return "none"
    if gap_class == "no_revision_evidence":
        return "revision_packet"
    if gap_class in {"revision_evidence_missing", "partial_revision_evidence"}:
        return "revision_evidence"
    return "packet_review"


def _normalize_keywords(value: str | None, *, default: str = "") -> str:
    return (value or default).lower().strip()


def _parse_iso_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _reference_time(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _record_hard_grounding_violation(
    checks: dict[str, Any],
    *,
    qid: str,
    plan_id: str,
    target_ref: str,
    code: str,
    details: dict[str, Any],
) -> None:
    checks["violations"].append(
        {
            "qid": qid,
            "plan_id": plan_id,
            "target_ref": target_ref,
            "code": code,
            "details": details,
        }
    )


def _evaluate_hard_grounding_policy(
    live_follow_by_qid: Mapping[str, list[dict[str, Any]]],
    *,
    reference_time: datetime,
) -> dict[str, Any]:
    checks: dict[str, Any] = {
        "allowed_source_classes": sorted(HARD_GROUNDING_ALLOWED_SOURCE_CLASSES),
        "max_revision_age_days": HARD_GROUNDING_MAX_REVISION_AGE_DAYS,
        "violations": [],
    }
    for qid, receipts in live_follow_by_qid.items():
        for receipt in receipts:
            plan_id = receipt.get("plan_id") or ""
            if not plan_id.startswith("hard_grounding_packet"):
                continue
            source_class = receipt.get("source_class") or ""
            target_ref = receipt.get("target_ref") or ""
            if source_class and source_class not in HARD_GROUNDING_ALLOWED_SOURCE_CLASSES:
                _record_hard_grounding_violation(
                    checks,
                    qid=qid,
                    plan_id=plan_id,
                    target_ref=target_ref,
                    code="unsupported_source_class",
                    details={"source_class": source_class},
                )
            timestamp_value = receipt.get("revision_timestamp")
            parsed = _parse_iso_timestamp(timestamp_value)
            if parsed:
                age = reference_time - parsed
                if age > timedelta(days=HARD_GROUNDING_MAX_REVISION_AGE_DAYS):
                    _record_hard_grounding_violation(
                        checks,
                        qid=qid,
                        plan_id=plan_id,
                        target_ref=target_ref,
                        code="stale_revision",
                        details={
                            "revision_timestamp": timestamp_value,
                            "age_days": age.days,
                        },
                    )
    return checks


def _coverage_status_from_slot(slot: Mapping[str, Any] | None) -> str:
    if not isinstance(slot, Mapping):
        return "unknown"
    decision = _normalize_keywords(slot.get("coverage_decision"))
    packet_status = _normalize_keywords(slot.get("packet_status"))
    coverage_state = _normalize_keywords(slot.get("coverage_state"))
    if decision in {"hold", "abstain", "grounded"}:
        return decision
    if "hold" in packet_status or "hold" in coverage_state:
        return "hold"
    if "abstain" in packet_status or "abstain" in coverage_state:
        return "abstain"
    if packet_status or coverage_state:
        return "grounded"
    return "unknown"


def _routing_needs_for_packet(entry: Mapping[str, Any]) -> list[str]:
    needs: list[str] = []
    notes = _normalize_text(entry.get("revision_locked_notes")).lower()
    evidence = entry.get("revision_evidence") or []
    normalized_excerpts = [
        _normalize_text(item.get("excerpt_summary")).lower()
        for item in evidence
        if isinstance(item, Mapping)
    ]
    if any(keyword in notes for keyword in ("authority", "policy", "hold", "control", "governance")):
        needs.append("authority")
    if evidence or any(keyword in notes for keyword in ("reference", "citation", "source")) or any(
        "reference" in excerpt for excerpt in normalized_excerpts if excerpt
    ):
        needs.append("reference")
    if evidence or _normalize_keywords(entry.get("live_follow_status")) not in {"", "no_live_receipts"}:
        needs.append("follow")
    return sorted(dict.fromkeys(needs))


def build_grounding_depth_summary(
    *,
    fixture: Mapping[str, Any],
    max_packets: int | None = None,
    live_follow_results: Sequence[Mapping[str, Any]] | None = None,
    policy_reference_time: datetime | None = None,
) -> dict[str, Any]:
    live_follow_by_qid = _index_live_follow_results(live_follow_results)
    reference_time = _reference_time(policy_reference_time)
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
        qid = _normalize_text(sample.get("qid"))
        live_follow_receipts = live_follow_by_qid.get(qid, [])
        live_follow_status = (
            "live_receipts_fetched"
            if any(receipt.get("status") == "fetched" for receipt in live_follow_receipts)
            else "no_live_receipts"
        )
        packets.append(
            {
                "packet_id": _normalize_text(sample.get("packet_id")),
                "qid": qid,
                "revision_url": _normalize_text(sample.get("revision_url")),
                "revision_locked_notes": _normalize_text(sample.get("revision_locked_notes")),
                "grounding_status": status,
                "revision_evidence": evidence,
                "live_follow_status": live_follow_status,
                "live_follow_receipts": live_follow_receipts,
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
        "hard_grounding_policy_checks": _evaluate_hard_grounding_policy(
            live_follow_by_qid,
            reference_time=reference_time,
        ),
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
        live_follow_receipts = entry.get("live_follow_receipts") or []
        if live_follow_receipts:
            packet_record["live_follow_status"] = (
                _normalize_text(entry.get("live_follow_status")) or "live_receipts_fetched"
            )
            packet_record["live_follow_count"] = len(live_follow_receipts)
            packet_record["live_source_class_counts"] = {
                _normalize_text(item.get("source_class")): sum(
                    1
                    for receipt in live_follow_receipts
                    if _normalize_text(receipt.get("source_class"))
                    == _normalize_text(item.get("source_class"))
                )
                for item in live_follow_receipts
                if _normalize_text(item.get("source_class"))
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


def build_grounding_depth_priority_surface(
    *, grounding_summary: Mapping[str, Any]
) -> dict[str, Any]:
    queue: list[dict[str, Any]] = []
    missing_field_counts: dict[str, int] = {}
    gap_class_counts: dict[str, int] = {}
    recommended_follow_scope_counts: dict[str, int] = {}
    live_source_class_counts: dict[str, int] = {}
    live_follow_ready_count = 0
    for entry in grounding_summary.get("packets") or []:
        if not isinstance(entry, Mapping):
            continue
        grounding_status = _normalize_text(entry.get("grounding_status")) or "unknown"
        evidence = entry.get("revision_evidence") or []
        live_follow_receipts = entry.get("live_follow_receipts") or []
        live_follow_count = len(live_follow_receipts)
        missing_fields: list[str] = []
        for item in evidence:
            if isinstance(item, Mapping):
                missing_fields.extend(
                    str(value)
                    for value in item.get("missing_fields", [])
                    if _normalize_text(value)
                )
        missing_fields = sorted(set(missing_fields))
        evidence_count = len(evidence)
        if grounding_status == "grounded":
            priority_score = 0
        elif live_follow_count > 0:
            priority_score = max(len(missing_fields), 1)
        else:
            priority_score = max(len(missing_fields), 1) + (0 if evidence_count else 1)
        if grounding_status != "grounded" and live_follow_count > 0:
            gap_class = "live_receipts_ready_for_review"
            follow_scope = "packet_review"
            recommended_follow_target = "review_live_follow_receipts"
            bounded_follow_recommended = False
            live_follow_ready_count += 1
        else:
            gap_class = _grounding_gap_class(
                grounding_status=grounding_status,
                evidence_count=evidence_count,
                missing_fields=missing_fields,
            )
            follow_scope = _recommended_follow_scope(gap_class=gap_class)
            recommended_follow_target = (
                "revision_locked_evidence" if grounding_status != "grounded" else "none"
            )
            bounded_follow_recommended = grounding_status != "grounded"
        for field in missing_fields:
            missing_field_counts[field] = missing_field_counts.get(field, 0) + 1
        gap_class_counts[gap_class] = gap_class_counts.get(gap_class, 0) + 1
        recommended_follow_scope_counts[follow_scope] = (
            recommended_follow_scope_counts.get(follow_scope, 0) + 1
        )
        for receipt in live_follow_receipts:
            if not isinstance(receipt, Mapping):
                continue
            source_class = _normalize_text(receipt.get("source_class"))
            if source_class:
                live_source_class_counts[source_class] = (
                    live_source_class_counts.get(source_class, 0) + 1
                )
        queue.append(
            {
                "packet_id": _normalize_text(entry.get("packet_id")),
                "qid": _normalize_text(entry.get("qid")),
                "grounding_status": grounding_status,
                "priority_score": priority_score,
                "evidence_count": evidence_count,
                "missing_fields": missing_fields,
                "grounding_gap_class": gap_class,
                "revision_url": _normalize_text(entry.get("revision_url")),
                "live_follow_status": _normalize_text(entry.get("live_follow_status"))
                or "no_live_receipts",
                "live_follow_count": live_follow_count,
                "live_source_class_counts": {
                    _normalize_text(item.get("source_class")): sum(
                        1
                        for receipt in live_follow_receipts
                        if _normalize_text(receipt.get("source_class"))
                        == _normalize_text(item.get("source_class"))
                    )
                    for item in live_follow_receipts
                    if _normalize_text(item.get("source_class"))
                },
                "recommended_follow_target": recommended_follow_target,
                "recommended_follow_scope": follow_scope,
                "bounded_follow_recommended": bounded_follow_recommended,
            }
        )
    queue.sort(
        key=lambda row: (
            -int(row.get("priority_score") or 0),
            str(row.get("packet_id") or ""),
        )
    )
    for index, row in enumerate(queue, start=1):
        row["priority_rank"] = index
    unresolved = [row for row in queue if row["bounded_follow_recommended"]]
    dominant_gap_class = max(
        gap_class_counts.items(),
        key=lambda item: (item[1], item[0]),
        default=("grounded", 0),
    )[0]
    dominant_missing_field = max(
        missing_field_counts.items(),
        key=lambda item: (item[1], item[0]),
        default=("", 0),
    )[0]
    return {
        "schema_version": GROUNDING_PRIORITY_SURFACE_SCHEMA_VERSION,
        "lane_id": _normalize_text(grounding_summary.get("lane_id")),
        "packet_count": len(queue),
        "grounded_packet_count": sum(
            1 for row in queue if row["grounding_status"] == "grounded"
        ),
        "bounded_follow_candidate_count": len(unresolved),
        "live_follow_ready_count": live_follow_ready_count,
        "highest_priority_score": max((int(row.get("priority_score") or 0) for row in queue), default=0),
        "gap_class_counts": gap_class_counts,
        "dominant_gap_class": dominant_gap_class,
        "missing_field_counts": missing_field_counts,
        "dominant_missing_field": dominant_missing_field,
        "recommended_follow_scope_counts": recommended_follow_scope_counts,
        "live_source_class_counts": live_source_class_counts,
        "queue": queue,
    }


def build_grounding_depth_routing_report(
    *,
    grounding_summary: Mapping[str, Any],
    coverage_index: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    priority_surface = build_grounding_depth_priority_surface(
        grounding_summary=grounding_summary
    )
    priority_map: dict[str, Mapping[str, Any]] = {
        _normalize_text(row.get("packet_id")): row
        for row in priority_surface.get("queue", [])
        if _normalize_text(row.get("packet_id"))
    }
    coverage_slots: dict[str, Mapping[str, Any]] = {}
    if isinstance(coverage_index, Mapping):
        for slot in coverage_index.get("packet_slots") or []:
            if not isinstance(slot, Mapping):
                continue
            packet_id = _normalize_text(slot.get("packet_id"))
            if packet_id:
                coverage_slots[packet_id] = slot

    coverage_counts: dict[str, int] = {"grounded": 0, "hold": 0, "abstain": 0, "unknown": 0}
    report: list[dict[str, Any]] = []
    for entry in grounding_summary.get("packets") or []:
        if not isinstance(entry, Mapping):
            continue
        packet_id = _normalize_text(entry.get("packet_id"))
        qid = _normalize_text(entry.get("qid"))
        priority_row = priority_map.get(packet_id, {})
        coverage_status = _coverage_status_from_slot(coverage_slots.get(packet_id))
        coverage_counts[coverage_status] = coverage_counts.get(coverage_status, 0) + 1
        routing_needs = _routing_needs_for_packet(entry)
        report.append(
            {
                "packet_id": packet_id,
                "qid": qid,
                "grounding_status": priority_row.get("grounding_status") or _normalize_text(
                    entry.get("grounding_status")
                ),
                "coverage_status": coverage_status,
                "routing_needs": routing_needs,
                "priority_score": priority_row.get("priority_score") or 0,
                "evidence_count": priority_row.get("evidence_count")
                or len(entry.get("revision_evidence") or []),
                "grounding_gap_class": priority_row.get("grounding_gap_class")
                or _normalize_text(entry.get("grounding_status")),
                "recommended_follow_scope": priority_row.get("recommended_follow_scope")
                or "unknown",
                "recommended_follow_target": priority_row.get("recommended_follow_target")
                or "",
                "live_follow_status": priority_row.get("live_follow_status")
                or _normalize_text(entry.get("live_follow_status")),
                "live_follow_count": priority_row.get("live_follow_count") or 0,
            }
        )
    return {
        "schema_version": GROUNDING_ROUTING_SCHEMA_VERSION,
        "lane_id": _normalize_text(grounding_summary.get("lane_id")),
        "packet_count": len(report),
        "grounded_packet_count": coverage_counts.get("grounded", 0),
        "hold_count": coverage_counts.get("hold", 0),
        "abstain_count": coverage_counts.get("abstain", 0),
        "unknown_coverage_count": coverage_counts.get("unknown", 0),
        "coverage_counts": coverage_counts,
        "routing_report": report,
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
