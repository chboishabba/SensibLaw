from __future__ import annotations

from collections import Counter
from pathlib import Path
import json
import re
from typing import Any, Callable, Mapping, Sequence

from .wikidata import ENTITY_EXPORT_TEMPLATE, MEDIAWIKI_API_ENDPOINT, REQUEST_HEADERS
from .wikidata_nat_live_follow_campaign import build_wikidata_nat_live_follow_campaign_plan


LIVE_FOLLOW_RESULT_SCHEMA_VERSION = "sl.wikidata_nat.live_follow_result.v0_1"
POLICY_RISK_PREFLIGHT_SCHEMA_VERSION = "sl.wikidata_nat.policy_risk_population_preview_preflight.v0_1"


JsonFetcher = Callable[..., Any]
TextFetcher = Callable[..., tuple[str, str, str]]

_SPLIT_HEAVY_CATEGORY_ID = "split_heavy_business_family"
_SPLIT_HEAVY_CAMPAIGN_RULE = "local_packet_first_bounded_live_follow_only"
_SPLIT_HEAVY_MAX_HOPS = 2
_SPLIT_HEAVY_ALLOWED_SOURCE_CLASSES = (
    "named_query_link",
    "named_revision_locked_source",
    "named_reference_url",
)


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _normalize_filters(values: Sequence[str] | None) -> set[str]:
    return {text for item in values or [] if (text := _stringify(item).strip())}


def _http_get_json(
    url: str,
    *,
    params: Mapping[str, Any] | None = None,
    timeout_seconds: int = 30,
) -> Any:
    import requests

    response = requests.get(
        url,
        params=params,
        headers=REQUEST_HEADERS,
        timeout=max(1, int(timeout_seconds)),
    )
    response.raise_for_status()
    return response.json()


def _http_get_text(
    url: str,
    *,
    timeout_seconds: int = 30,
) -> tuple[str, str, str]:
    import requests

    response = requests.get(
        url,
        headers=REQUEST_HEADERS,
        timeout=max(1, int(timeout_seconds)),
    )
    response.raise_for_status()
    return response.url, _stringify(response.headers.get("content-type")), response.text


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _fixtures_root() -> Path:
    return _repo_root() / "tests" / "fixtures" / "wikidata"


def _read_json_file(path: Path) -> Mapping[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, Mapping) else None


def _extract_url(text: str) -> str | None:
    match = re.search(r"https?://\S+", text)
    if not match:
        return None
    return match.group(0).rstrip(").,;")


def _sidecar_fixture_for_qid(qid: str) -> Mapping[str, Any] | None:
    return _read_json_file(
        _fixtures_root() / f"wikidata_nat_review_packet_{qid}_sidecar_20260402.json"
    )


def _attachment_coverage_fixture() -> Mapping[str, Any] | None:
    return _read_json_file(
        _fixtures_root() / "wikidata_nat_review_packet_attachment_coverage_20260401.json"
    )


def _cohort_b_packet_input_fixture() -> Mapping[str, Any] | None:
    return _read_json_file(
        _fixtures_root() / "wikidata_nat_cohort_b_operator_packet_input_20260402.json"
    )


def _packet_slot_from_attachment_coverage(
    *,
    packet_id: str,
    qid: str,
) -> Mapping[str, Any] | None:
    payload = _attachment_coverage_fixture()
    if not payload:
        return None
    packet_slots = payload.get("packet_slots")
    if not isinstance(packet_slots, list):
        return None
    for slot in packet_slots:
        if not isinstance(slot, Mapping):
            continue
        if packet_id and _stringify(slot.get("packet_id")).strip() == packet_id:
            return slot
        if qid and _stringify(slot.get("review_entity_qid")).strip() == qid:
            return slot
    return None


def _query_link_from_local_surface(row: Mapping[str, Any]) -> str | None:
    qid = _stringify(row.get("qid")).strip()
    target_ref = _stringify(row.get("target_ref")).strip()
    sidecar = _sidecar_fixture_for_qid(qid) if qid else None
    if sidecar:
        page_signals = sidecar.get("page_signals")
        if isinstance(page_signals, Mapping):
            query_links = page_signals.get("query_links")
            if isinstance(query_links, list):
                for item in query_links:
                    text = _stringify(item).strip()
                    if text:
                        return text
        follow_receipts = sidecar.get("follow_receipts")
        if isinstance(follow_receipts, list):
            for receipt in follow_receipts:
                if not isinstance(receipt, Mapping):
                    continue
                text = _stringify(receipt.get("url")).strip()
                if text:
                    return text

    slot = _packet_slot_from_attachment_coverage(packet_id=target_ref, qid=qid)
    if not slot:
        return None
    packet_summary = slot.get("packet_summary")
    if not isinstance(packet_summary, Mapping):
        return None
    parsed_page = packet_summary.get("parsed_page")
    if not isinstance(parsed_page, Mapping):
        return None
    page_signals = parsed_page.get("page_signals")
    if isinstance(page_signals, Mapping):
        query_links = page_signals.get("query_links")
        if isinstance(query_links, list):
            for item in query_links:
                text = _stringify(item).strip()
                if text:
                    return text
    task_buckets = parsed_page.get("task_buckets")
    if isinstance(task_buckets, Mapping):
        queries = task_buckets.get("queries")
        if isinstance(queries, list):
            for item in queries:
                url = _extract_url(_stringify(item))
                if url:
                    return url
    return None


def _cohort_c_reference_url_for_qid(qid: str) -> str | None:
    for filename in (
        "wikidata_nat_cohort_c_operator_evidence_packet_20260404.json",
        "wikidata_nat_cohort_c_operator_packet_extension_20260403.json",
    ):
        payload = _read_json_file(_fixtures_root() / filename)
        rows: Sequence[Any]
        if not payload:
            continue
        if isinstance(payload, Mapping):
            evidence_rows = payload.get("evidence_rows")
            rows = evidence_rows if isinstance(evidence_rows, list) else []
        elif isinstance(payload, list):
            rows = payload
        else:
            rows = []
        for item in rows:
            if not isinstance(item, Mapping):
                continue
            if _stringify(item.get("qid")).strip() != qid:
                continue
            anchor = _stringify(item.get("reference_anchor")).strip()
            url = _extract_url(anchor)
            if url:
                return url
    return None


def _policy_risk_evidence_fixture() -> Mapping[str, Any] | None:
    return _read_json_file(
        _fixtures_root() / "wikidata_nat_cohort_c_operator_evidence_packet_20260404.json"
    )


def _policy_risk_evidence_by_qid() -> dict[str, Mapping[str, Any]]:
    payload = _policy_risk_evidence_fixture()
    if not payload:
        return {}
    evidence_rows = payload.get("evidence_rows")
    if not isinstance(evidence_rows, list):
        return {}
    index: dict[str, Mapping[str, Any]] = {}
    for row in evidence_rows:
        if not isinstance(row, Mapping):
            continue
        qid = _stringify(row.get("qid")).strip()
        if qid:
            index[qid] = row
    return index


def _contains_policy_keyword(text: str | Mapping[str, Any] | None, *, keywords: Sequence[str]) -> bool:
    normalized = _stringify(text).lower()
    if not normalized:
        return False
    return any(keyword in normalized for keyword in keywords)


def _policy_risk_authority_score(
    row: Mapping[str, Any],
    evidence: Mapping[str, Any] | None,
) -> float:
    score = 0.5
    policy_keywords = ("policy", "hold", "governance", "authority", "risk")
    if _contains_policy_keyword(row.get("stop_condition"), keywords=policy_keywords):
        score += 0.25
    if _contains_policy_keyword(row.get("uncertainty_kind"), keywords=policy_keywords):
        score += 0.15
    if evidence:
        hold_text = evidence.get("operator_hold_reason") or evidence.get("preview_hold_reason")
        if _contains_policy_keyword(hold_text, keywords=policy_keywords):
            score += 0.2
        if _stringify(evidence.get("reference_anchor")).strip():
            score += 0.15
    return round(min(score, 1.0), 3)


def _policy_risk_certainty_score(evidence: Mapping[str, Any] | None) -> float:
    if not evidence:
        return 0.35
    status = _stringify(evidence.get("p459_status")).lower()
    if status in {"missing", "non-ghg-protocol"}:
        base = 0.8
    elif status == "ghg protocol":
        base = 0.3
    else:
        base = 0.6
    hint = evidence.get("qualifier_hint")
    hint_count = (
        len([item for item in hint if _stringify(item).strip()])
        if isinstance(hint, Sequence)
        else 0
    )
    return round(min(base + hint_count * 0.05, 1.0), 3)


def _policy_risk_follow_opportunity(evidence: Mapping[str, Any] | None) -> bool:
    if not evidence:
        return False
    if _stringify(evidence.get("reference_anchor")).strip():
        return True
    hint = evidence.get("qualifier_hint")
    if isinstance(hint, Sequence):
        return any(_stringify(item).strip() for item in hint)
    return False


def _policy_risk_routing_needs(evidence: Mapping[str, Any] | None) -> list[str]:
    needs: list[str] = []
    if evidence and _contains_policy_keyword(
        evidence.get("operator_hold_reason") or evidence.get("preview_hold_reason"),
        keywords=("policy", "hold", "governance"),
    ):
        needs.append("authority")
    if evidence and _stringify(evidence.get("reference_anchor")).strip():
        needs.append("reference")
    if _policy_risk_follow_opportunity(evidence):
        needs.append("follow")
    return sorted(dict.fromkeys(needs))


def _policy_risk_failure_modes(
    row: Mapping[str, Any],
    evidence: Mapping[str, Any] | None,
    coverage_status: str,
) -> list[str]:
    modes: list[str] = []
    if not _stringify(row.get("qid")).strip():
        modes.append("missing_qid")
    if not _stringify(row.get("stop_condition")).strip():
        modes.append("missing_stop_condition")
    if evidence is None:
        modes.append("missing_policy_risk_evidence")
    if coverage_status not in {"grounded", "hold", "abstain", "unknown"}:
        modes.append("unknown_coverage_status")
    return sorted(dict.fromkeys(modes))


def _reference_url_from_local_surface(row: Mapping[str, Any]) -> str | None:
    qid = _stringify(row.get("qid")).strip()
    target_ref = _stringify(row.get("target_ref")).strip()
    sidecar = _sidecar_fixture_for_qid(qid) if qid else None
    if sidecar:
        source_surface = sidecar.get("source_surface")
        if isinstance(source_surface, Mapping):
            origin = source_surface.get("origin")
            if isinstance(origin, Mapping):
                text = _stringify(origin.get("source_url")).strip()
                if text:
                    return text
        follow_receipts = sidecar.get("follow_receipts")
        if isinstance(follow_receipts, list):
            for receipt in follow_receipts:
                if not isinstance(receipt, Mapping):
                    continue
                text = _stringify(receipt.get("url")).strip()
                if text and "w.wiki" not in text:
                    return text

    slot = _packet_slot_from_attachment_coverage(packet_id=target_ref, qid=qid)
    if slot:
        source_surface = slot.get("source_surface")
        if isinstance(source_surface, Mapping):
            origin = source_surface.get("origin")
            if isinstance(origin, Mapping):
                text = _stringify(origin.get("source_url")).strip()
                if text:
                    return text

    grounding_batch = _read_json_file(_fixtures_root() / "wikidata_nat_grounding_depth_batch_20260402.json")
    if grounding_batch:
        attachments = grounding_batch.get("attachments")
        if isinstance(attachments, list):
            for attachment in attachments:
                if not isinstance(attachment, Mapping):
                    continue
                if qid and _stringify(attachment.get("qid")).strip() != qid:
                    continue
                evidence = attachment.get("evidence")
                if isinstance(evidence, list):
                    for entry in evidence:
                        if not isinstance(entry, Mapping):
                            continue
                        text = _stringify(entry.get("follow_receipt_url")).strip()
                        if text:
                            return text
                text = _stringify(attachment.get("revision_url")).strip()
                if text:
                    return text

    cohort_c_url = _cohort_c_reference_url_for_qid(qid)
    if cohort_c_url:
        return cohort_c_url
    cohort_b_packet_input = _cohort_b_packet_input_fixture()
    if cohort_b_packet_input:
        review_bucket_rows = cohort_b_packet_input.get("review_bucket_rows")
        if isinstance(review_bucket_rows, list):
            for bucket_row in review_bucket_rows:
                if not isinstance(bucket_row, Mapping):
                    continue
                bucket_row_id = _stringify(bucket_row.get("row_id")).strip()
                bucket_qid = _stringify(bucket_row.get("entity_qid")).strip()
                if target_ref and bucket_row_id != target_ref:
                    continue
                if qid and bucket_qid and bucket_qid != qid:
                    continue
                text = _stringify(bucket_row.get("reference_url")).strip()
                if text:
                    return text
                reference_urls = bucket_row.get("reference_urls")
                if isinstance(reference_urls, list):
                    for item in reference_urls:
                        text = _stringify(item).strip()
                        if text:
                            return text
    return None


def _fetch_recent_revisions(
    qid: str,
    *,
    timeout_seconds: int,
    fetch_json: JsonFetcher,
) -> list[dict[str, Any]]:
    payload = fetch_json(
        MEDIAWIKI_API_ENDPOINT,
        params={
            "action": "query",
            "prop": "revisions",
            "titles": qid,
            "rvlimit": 2,
            "rvprop": "ids|timestamp",
            "format": "json",
        },
        timeout_seconds=timeout_seconds,
    )
    pages = payload.get("query", {}).get("pages", {})
    if not isinstance(pages, Mapping) or not pages:
        return []
    page = next(iter(pages.values()))
    revisions = page.get("revisions", [])
    if not isinstance(revisions, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in revisions:
        if not isinstance(item, Mapping):
            continue
        revid = item.get("revid")
        timestamp = item.get("timestamp")
        if revid is None or timestamp is None:
            continue
        rows.append(
            {
                "revid": int(revid),
                "timestamp": _stringify(timestamp),
            }
        )
    return rows


def _entity_summary(payload: Mapping[str, Any], *, qid: str) -> dict[str, Any]:
    entities = payload.get("entities")
    if not isinstance(entities, Mapping):
        return {
            "qid": qid,
            "entity_present": False,
            "claim_property_count": 0,
            "label": qid,
        }
    entity = entities.get(qid)
    if not isinstance(entity, Mapping):
        return {
            "qid": qid,
            "entity_present": False,
            "claim_property_count": 0,
            "label": qid,
        }
    labels = entity.get("labels")
    english = labels.get("en") if isinstance(labels, Mapping) else None
    claims = entity.get("claims")
    return {
        "qid": qid,
        "entity_present": True,
        "label": _stringify(english.get("value")) if isinstance(english, Mapping) else qid,
        "claim_property_count": len(claims) if isinstance(claims, Mapping) else 0,
    }


def _fetch_named_revision_locked_source(
    row: Mapping[str, Any],
    *,
    timeout_seconds: int,
    fetch_json: JsonFetcher,
) -> dict[str, Any]:
    qid = _stringify(row.get("qid")).strip()
    if not qid:
        raise ValueError("plan row requires qid for named_revision_locked_source")
    revisions = _fetch_recent_revisions(
        qid,
        timeout_seconds=timeout_seconds,
        fetch_json=fetch_json,
    )
    if not revisions:
        raise ValueError(f"no revisions returned for {qid}")
    selected = revisions[0]
    revid = int(selected["revid"])
    export_url = ENTITY_EXPORT_TEMPLATE.format(qid=qid, revid=revid)
    entity_export = fetch_json(
        export_url,
        timeout_seconds=timeout_seconds,
    )
    if not isinstance(entity_export, Mapping):
        raise ValueError(f"entity export must be an object for {qid}@{revid}")
    return {
        "status": "fetched",
        "source_class": "named_revision_locked_source",
        "qid": qid,
        "revision": {
            "retrieval_method": "wiki_revision",
            "revision_id": str(revid),
            "revision_timestamp": _stringify(selected.get("timestamp")),
            "revision_url": f"https://www.wikidata.org/w/index.php?title={qid}&oldid={revid}",
        },
        "entity_summary": _entity_summary(entity_export, qid=qid),
    }


def _fetch_named_query_link(
    row: Mapping[str, Any],
    *,
    timeout_seconds: int,
    fetch_text: TextFetcher,
) -> dict[str, Any]:
    query_url = _query_link_from_local_surface(row)
    if not query_url:
        raise ValueError("no local query link available for named_query_link")
    final_url, content_type, body = fetch_text(
        query_url,
        timeout_seconds=timeout_seconds,
    )
    title_match = re.search(r"<title>(.*?)</title>", body, re.IGNORECASE | re.DOTALL)
    title = re.sub(r"\s+", " ", title_match.group(1)).strip() if title_match else ""
    text_excerpt = re.sub(r"\s+", " ", body).strip()[:240]
    return {
        "status": "fetched",
        "source_class": "named_query_link",
        "qid": _stringify(row.get("qid")).strip() or None,
        "query_link": {
            "original_url": query_url,
            "final_url": final_url,
            "content_type": content_type,
            "title": title or None,
            "text_excerpt": text_excerpt or None,
        },
    }


def _fetch_named_reference_url(
    row: Mapping[str, Any],
    *,
    timeout_seconds: int,
    fetch_text: TextFetcher,
) -> dict[str, Any]:
    reference_url = _reference_url_from_local_surface(row)
    if not reference_url:
        raise ValueError("no local reference url available for named_reference_url")
    final_url, content_type, body = fetch_text(
        reference_url,
        timeout_seconds=timeout_seconds,
    )
    title_match = re.search(r"<title>(.*?)</title>", body, re.IGNORECASE | re.DOTALL)
    title = re.sub(r"\s+", " ", title_match.group(1)).strip() if title_match else ""
    text_excerpt = re.sub(r"\s+", " ", body).strip()[:240]
    return {
        "status": "fetched",
        "source_class": "named_reference_url",
        "qid": _stringify(row.get("qid")).strip() or None,
        "reference_url": {
            "original_url": reference_url,
            "final_url": final_url,
            "content_type": content_type,
            "title": title or None,
            "text_excerpt": text_excerpt or None,
        },
    }


def _attempt_source_class(
    row: Mapping[str, Any],
    source_class: str,
    *,
    timeout_seconds: int,
    fetch_json: JsonFetcher,
    fetch_text: TextFetcher,
) -> dict[str, Any]:
    if source_class == "named_query_link":
        return _fetch_named_query_link(
            row,
            timeout_seconds=timeout_seconds,
            fetch_text=fetch_text,
        )
    if source_class == "named_reference_url":
        return _fetch_named_reference_url(
            row,
            timeout_seconds=timeout_seconds,
            fetch_text=fetch_text,
        )
    if source_class == "named_revision_locked_source":
        return _fetch_named_revision_locked_source(
            row,
            timeout_seconds=timeout_seconds,
            fetch_json=fetch_json,
        )
    return {
        "status": "unsupported_source_class",
        "source_class": source_class,
        "reason": f"bounded executor does not yet implement {source_class}",
    }


def execute_wikidata_nat_live_follow_plan(
    plan: Mapping[str, Any],
    *,
    category_ids: Sequence[str] | None = None,
    plan_ids: Sequence[str] | None = None,
    limit: int | None = None,
    timeout_seconds: int = 30,
    fetch_json: JsonFetcher | None = None,
    fetch_text: TextFetcher | None = None,
) -> dict[str, Any]:
    rows = plan.get("plan_rows")
    if not isinstance(rows, list):
        raise ValueError("plan requires plan_rows")
    wanted_categories = _normalize_filters(category_ids)
    wanted_plan_ids = _normalize_filters(plan_ids)
    selected: list[Mapping[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        category_id = _stringify(row.get("category_id")).strip()
        plan_id = _stringify(row.get("plan_id")).strip()
        if wanted_categories and category_id not in wanted_categories:
            continue
        if wanted_plan_ids and plan_id not in wanted_plan_ids:
            continue
        selected.append(row)
    if limit is not None:
        selected = selected[: max(0, int(limit))]

    fetcher = fetch_json or _http_get_json
    text_fetcher = fetch_text or _http_get_text
    result_rows: list[dict[str, Any]] = []
    source_counter: Counter[str] = Counter()
    status_counter: Counter[str] = Counter()
    for row in selected:
        attempts: list[dict[str, Any]] = []
        selected_result: dict[str, Any] | None = None
        error_result: dict[str, Any] | None = None
        for source_class in row.get("source_order") or []:
            source_text = _stringify(source_class).strip()
            if not source_text:
                continue
            try:
                attempt = _attempt_source_class(
                    row,
                    source_text,
                    timeout_seconds=timeout_seconds,
                    fetch_json=fetcher,
                    fetch_text=text_fetcher,
                )
            except Exception as exc:
                attempt = {
                    "status": "fetch_error",
                    "source_class": source_text,
                    "reason": _stringify(exc),
                }
            attempts.append(attempt)
            if attempt.get("status") == "fetched":
                selected_result = attempt
                break
            if attempt.get("status") == "fetch_error" and error_result is None:
                error_result = attempt
        final_result = selected_result or error_result
        final_status = _stringify(final_result.get("status") if final_result else "").strip()
        if not final_status:
            final_status = _stringify(attempts[-1]["status"]).strip() if attempts else "no_attempts"
        chosen_source = _stringify(
            final_result.get("source_class") if final_result else attempts[-1].get("source_class") if attempts else ""
        ).strip() or None
        result = {
            "plan_id": _stringify(row.get("plan_id")).strip(),
            "category_id": _stringify(row.get("category_id")).strip(),
            "uncertainty_kind": _stringify(row.get("uncertainty_kind")).strip(),
            "target_ref": _stringify(row.get("target_ref")).strip(),
            "qid": _stringify(row.get("qid")).strip() or None,
            "status": final_status,
            "chosen_source_class": chosen_source,
            "attempts": attempts,
        }
        if final_result:
            result["evidence"] = final_result
        result_rows.append(result)
        status_counter[final_status] += 1
        if chosen_source:
            source_counter[chosen_source] += 1

    return {
        "schema_version": LIVE_FOLLOW_RESULT_SCHEMA_VERSION,
        "campaign_id": _stringify(plan.get("campaign_id")).strip(),
        "lane_id": _stringify(plan.get("lane_id")).strip(),
        "execution_mode": "bounded_live_follow",
        "selected_count": len(selected),
        "status_counts": dict(status_counter),
        "chosen_source_class_counts": dict(source_counter),
        "result_rows": result_rows,
    }


def build_policy_risk_population_preview_preflight(
    campaign: Mapping[str, Any],
    *,
    top_n: int = 2,
) -> dict[str, Any]:
    plan = build_wikidata_nat_live_follow_campaign_plan(campaign)
    target_rows = [
        row
        for row in plan.get("plan_rows") or []
        if _stringify(row.get("category_id")) == "policy_risk_population_preview"
    ]
    available = max(1, int(top_n or 1))
    failure_modes: list[str] = []
    if not target_rows:
        failure_modes.append("no_policy_risk_rows")
    evidence_index = _policy_risk_evidence_by_qid()
    ranking: list[dict[str, Any]] = []
    coverage_counts: Counter[str] = Counter()
    stop_conditions: set[str] = set()
    stop_signals: set[str] = set()
    for row in target_rows:
        qid = _stringify(row.get("qid")).strip()
        plan_id = _stringify(row.get("plan_id")).strip()
        stop_condition = _stringify(row.get("stop_condition")).strip()
        evidence = evidence_index.get(qid)
        coverage_status = (
            _stringify(evidence.get("promotion_guard")).strip().lower()
            if evidence
            else "unknown"
        )
        if not coverage_status:
            coverage_status = "unknown"
        coverage_counts[coverage_status] += 1
        if stop_condition:
            stop_conditions.add(stop_condition)
        stop_signals.add(f"coverage_{coverage_status}")
        authority_score = _policy_risk_authority_score(row, evidence)
        certainty_score = _policy_risk_certainty_score(evidence)
        follow_opportunity = _policy_risk_follow_opportunity(evidence)
        routing_needs = _policy_risk_routing_needs(evidence)
        failure_entries = _policy_risk_failure_modes(row, evidence, coverage_status)
        failure_modes.extend(failure_entries)
        ranking.append(
            {
                "plan_id": plan_id,
                "target_ref": _stringify(row.get("target_ref")).strip(),
                "qid": qid,
                "category_id": _stringify(row.get("category_id")).strip(),
                "stop_condition": stop_condition,
                "authority_score": authority_score,
                "certainty_score": certainty_score,
                "follow_opportunity": follow_opportunity,
                "routing_needs": routing_needs,
                "coverage_status": coverage_status,
                "failure_modes": failure_entries,
                "score": round(
                    authority_score + certainty_score + (0.25 if follow_opportunity else 0),
                    3,
                ),
            }
        )

    ranking.sort(key=lambda entry: (-entry["score"], entry["plan_id"]))
    selected = ranking[:available]
    for index, entry in enumerate(selected, start=1):
        entry["rank"] = index

    aggregated_failures = sorted(dict.fromkeys(mode for mode in failure_modes if mode))
    return {
        "schema_version": POLICY_RISK_PREFLIGHT_SCHEMA_VERSION,
        "campaign_id": _stringify(plan.get("campaign_id")).strip(),
        "campaign_rule": _stringify(plan.get("campaign_rule")).strip(),
        "lane_id": _stringify(plan.get("lane_id")).strip(),
        "plan_schema_version": _stringify(plan.get("schema_version")).strip(),
        "top_n": available,
        "candidate_count": len(target_rows),
        "coverage_counts": dict(coverage_counts),
        "stop_conditions": sorted({item for item in stop_conditions if item}),
        "stop_signals": sorted(stop_signals),
        "failure_modes": aggregated_failures,
        "candidates": selected,
    }


def execute_wikidata_nat_live_follow_campaign(
    campaign: Mapping[str, Any],
    *,
    category_ids: Sequence[str] | None = None,
    plan_ids: Sequence[str] | None = None,
    limit: int | None = None,
    timeout_seconds: int = 30,
    fetch_json: JsonFetcher | None = None,
    fetch_text: TextFetcher | None = None,
) -> dict[str, Any]:
    plan = build_wikidata_nat_live_follow_campaign_plan(campaign)
    result = execute_wikidata_nat_live_follow_plan(
        plan,
        category_ids=category_ids,
        plan_ids=plan_ids,
        limit=limit,
        timeout_seconds=timeout_seconds,
        fetch_json=fetch_json,
        fetch_text=fetch_text,
    )
    result["plan_schema_version"] = _stringify(plan.get("schema_version")).strip()
    result["campaign_rule"] = _stringify(campaign.get("campaign_rule")).strip()
    return result


def _split_heavy_plan_rows(plan: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = plan.get("plan_rows")
    if not isinstance(rows, list):
        return []
    return [
        row
        for row in rows
        if isinstance(row, Mapping)
        and _stringify(row.get("category_id")).strip() == _SPLIT_HEAVY_CATEGORY_ID
    ]


def _validate_split_heavy_business_family_plan(plan: Mapping[str, Any]) -> None:
    rule = _stringify(plan.get("campaign_rule")).strip()
    if rule != _SPLIT_HEAVY_CAMPAIGN_RULE:
        raise ValueError(
            f"split-heavy lane requires campaign_rule={_SPLIT_HEAVY_CAMPAIGN_RULE}, got {rule or '<missing>'}"
        )
    rows = _split_heavy_plan_rows(plan)
    if not rows:
        raise ValueError("split-heavy lane requires plan rows for split_heavy_business_family")
    for row in rows:
        max_hops = int(row.get("max_hops") or 0)
        if max_hops != _SPLIT_HEAVY_MAX_HOPS:
            raise ValueError("split-heavy lane requires max_hops=2")
        if not row.get("local_first"):
            raise ValueError("split-heavy lane expects local_packet_first ordering")
        source_order = [cls for cls in (row.get("source_order") or []) if isinstance(cls, str)]
        invalid = [cls for cls in source_order if cls not in _SPLIT_HEAVY_ALLOWED_SOURCE_CLASSES]
        if invalid:
            raise ValueError(
                f"split-heavy lane does not support source classes {invalid}; open-ended searches are blocked"
            )


def execute_split_heavy_business_family_lane(
    campaign: Mapping[str, Any],
    *,
    limit: int | None = None,
    timeout_seconds: int = 30,
    fetch_json: JsonFetcher | None = None,
    fetch_text: TextFetcher | None = None,
) -> dict[str, Any]:
    plan = build_wikidata_nat_live_follow_campaign_plan(campaign)
    _validate_split_heavy_business_family_plan(plan)
    return execute_wikidata_nat_live_follow_plan(
        plan,
        category_ids=[_SPLIT_HEAVY_CATEGORY_ID],
        limit=limit,
        timeout_seconds=timeout_seconds,
        fetch_json=fetch_json,
        fetch_text=fetch_text,
    )


__all__ = [
    "LIVE_FOLLOW_RESULT_SCHEMA_VERSION",
    "POLICY_RISK_PREFLIGHT_SCHEMA_VERSION",
    "execute_wikidata_nat_live_follow_campaign",
    "execute_wikidata_nat_live_follow_plan",
    "build_policy_risk_population_preview_preflight",
    "execute_split_heavy_business_family_lane",
]
