from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from src.reporting.structure_report import TextUnit

from .read_model import (
    OBSERVATION_PREDICATE_TO_FAMILY,
    build_fact_intake_payload_from_text_units,
    build_fact_intake_report,
    build_fact_review_operator_views,
    build_fact_review_run_summary,
    persist_fact_intake_payload,
)

PERSONAL_HANDOFF_REPORT_VERSION = "personal.handoff.report.v1"

_DEFAULT_SOURCE_SIGNAL_CLASSES: dict[str, list[str]] = {
    "personal_note": ["user_authored", "client_account"],
    "chat_archive_sample": ["user_authored", "client_account"],
    "facebook_messages_archive_sample": ["user_authored", "client_account"],
    "openrecall_capture": ["user_authored", "client_account"],
    "documentary_record": ["documentary_record", "third_party_record"],
    "professional_note": ["professional_note", "professional_interpretation", "later_annotation"],
    "support_worker_note": ["support_worker_note", "later_annotation"],
}

_RECIPIENT_PROFILES: dict[str, dict[str, str]] = {
    "lawyer": {"title": "Lawyer handoff", "preferred_operator_view": "professional_handoff"},
    "doctor": {"title": "Doctor handoff", "preferred_operator_view": "professional_handoff"},
    "advocate": {"title": "Advocate handoff", "preferred_operator_view": "trauma_handoff"},
    "regulator": {"title": "Regulator handoff", "preferred_operator_view": "intake_triage"},
}

_EXPORT_POLICY_ORDER = {"full": 0, "redact": 1, "omit": 2}


@dataclass(frozen=True)
class EntryPolicy:
    unit_id: str
    share_with: tuple[str, ...]
    text_export_policy: str
    signal_classes: tuple[str, ...]
    protected_disclosure_only: bool
    protected_disclosure_reason: str | None


@dataclass(frozen=True)
class ProtectedDisclosureEnvelope:
    enabled: bool
    disclosure_level: str
    envelope_policy: str
    handling_notice: str
    allowed_recipient_profiles: tuple[str, ...]


def _stable_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256_payload(payload: object) -> str:
    return hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()


def _created_at_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_profile(profile: str) -> str:
    text = str(profile or "").strip().casefold()
    if text not in _RECIPIENT_PROFILES:
        raise ValueError(f"unsupported recipient_profile: {profile}")
    return text


def _normalize_signal_classes(entry: Mapping[str, Any]) -> list[str]:
    explicit = entry.get("signal_classes")
    if isinstance(explicit, list) and explicit:
        return [str(value) for value in explicit if str(value).strip()]
    return list(_DEFAULT_SOURCE_SIGNAL_CLASSES.get(str(entry.get("source_type") or "").strip(), []))


def _normalize_share_with(entry: Mapping[str, Any]) -> list[str]:
    raw = entry.get("share_with")
    if not isinstance(raw, list) or not raw:
        return ["lawyer", "doctor", "advocate", "regulator"]
    return [_normalize_profile(str(value)) for value in raw]


def _normalize_text_export_policy(entry: Mapping[str, Any]) -> str:
    policy = str(entry.get("text_export_policy") or "full").strip().casefold()
    if policy not in _EXPORT_POLICY_ORDER:
        raise ValueError(f"unsupported text_export_policy: {policy}")
    return policy


def _normalize_protected_disclosure_reason(entry: Mapping[str, Any]) -> str | None:
    text = str(entry.get("protected_disclosure_reason") or "").strip()
    return text or None


def _build_protected_disclosure_envelope(handoff_flags: Mapping[str, Any]) -> ProtectedDisclosureEnvelope:
    raw = handoff_flags.get("protected_disclosure")
    if not isinstance(raw, Mapping) or not bool(raw.get("enabled")):
        return ProtectedDisclosureEnvelope(
            enabled=False,
            disclosure_level="none",
            envelope_policy="none",
            handling_notice="",
            allowed_recipient_profiles=(),
        )
    allowed_raw = raw.get("allowed_recipient_profiles")
    if isinstance(allowed_raw, list) and allowed_raw:
        allowed = tuple(_normalize_profile(str(value)) for value in allowed_raw)
    else:
        allowed = ("lawyer", "regulator")
    return ProtectedDisclosureEnvelope(
        enabled=True,
        disclosure_level=str(raw.get("disclosure_level") or "protected_disclosure_v1"),
        envelope_policy=str(raw.get("envelope_policy") or "protected_disclosure_local_only_v1"),
        handling_notice=str(
            raw.get("handling_notice")
            or "Protected-disclosure material must remain local-only, do-not-sync, and scoped to permitted recipients."
        ),
        allowed_recipient_profiles=allowed,
    )


def _build_entry_policies(entries: Iterable[Mapping[str, Any]]) -> dict[str, EntryPolicy]:
    policies: dict[str, EntryPolicy] = {}
    for entry in entries:
        unit_id = str(entry.get("unit_id") or "").strip()
        if not unit_id:
            raise ValueError("entry.unit_id is required")
        policies[unit_id] = EntryPolicy(
            unit_id=unit_id,
            share_with=tuple(_normalize_share_with(entry)),
            text_export_policy=_normalize_text_export_policy(entry),
            signal_classes=tuple(_normalize_signal_classes(entry)),
            protected_disclosure_only=bool(entry.get("protected_disclosure_only")),
            protected_disclosure_reason=_normalize_protected_disclosure_reason(entry),
        )
    return policies


def _load_units(entries: Iterable[Mapping[str, Any]]) -> list[TextUnit]:
    units: list[TextUnit] = []
    for entry in entries:
        unit_id = str(entry.get("unit_id") or "").strip()
        source_id = str(entry.get("source_id") or "").strip()
        source_type = str(entry.get("source_type") or "").strip()
        text = str(entry.get("text") or "").strip()
        if not unit_id or not source_id or not source_type or not text:
            raise ValueError("entries require unit_id, source_id, source_type, and text")
        units.append(TextUnit(unit_id, source_id, source_type, text))
    if not units:
        raise ValueError("at least one entry is required")
    return units


def _set_source_signal_classes(payload: dict[str, Any], entry_policies: Mapping[str, EntryPolicy]) -> None:
    for source in payload.get("sources", []):
        unit_id = str(source.get("source_ref") or "").strip()
        policy = entry_policies.get(unit_id)
        if policy is None:
            continue
        provenance = dict(source.get("provenance") or {})
        provenance["source_signal_classes"] = list(policy.signal_classes)
        provenance["share_with"] = list(policy.share_with)
        provenance["text_export_policy"] = policy.text_export_policy
        provenance["protected_disclosure_only"] = policy.protected_disclosure_only
        if policy.protected_disclosure_reason:
            provenance["protected_disclosure_reason"] = policy.protected_disclosure_reason
        source["provenance"] = provenance


def _statement_index_by_unit_id(payload: Mapping[str, Any]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for index, statement in enumerate(payload.get("statements", [])):
        provenance = statement.get("provenance") if isinstance(statement.get("provenance"), Mapping) else {}
        unit_id = str(provenance.get("unit_id") or "").strip()
        if unit_id:
            mapping[unit_id] = index
    return mapping


def _fact_index_by_unit_id(payload: Mapping[str, Any]) -> dict[str, int]:
    statement_unit_ids: dict[str, str] = {}
    for statement in payload.get("statements", []):
        provenance = statement.get("provenance") if isinstance(statement.get("provenance"), Mapping) else {}
        unit_id = str(provenance.get("unit_id") or "").strip()
        statement_id = str(statement.get("statement_id") or "").strip()
        if unit_id and statement_id:
            statement_unit_ids[statement_id] = unit_id
    mapping: dict[str, int] = {}
    for index, fact in enumerate(payload.get("fact_candidates", [])):
        statement_id = str(fact.get("primary_statement_id") or "").strip()
        unit_id = statement_unit_ids.get(statement_id)
        if unit_id:
            mapping[unit_id] = index
    return mapping


def _append_observation(payload: dict[str, Any], observation: Mapping[str, Any], statement_index_by_unit_id: Mapping[str, int]) -> None:
    unit_id = str(observation.get("unit_id") or "").strip()
    statement_index = statement_index_by_unit_id.get(unit_id)
    if statement_index is None:
        raise ValueError(f"observation references unknown unit_id: {unit_id}")
    predicate_key = str(observation.get("predicate_key") or "").strip()
    if predicate_key not in OBSERVATION_PREDICATE_TO_FAMILY:
        raise ValueError(f"unsupported observation predicate_key: {predicate_key}")
    statement = payload["statements"][statement_index]
    excerpt = payload["excerpts"][statement_index]
    source = next((row for row in payload["sources"] if row["source_id"] == excerpt["source_id"]), payload["sources"][0])
    object_text = str(observation.get("object_text") or "").strip()
    if not object_text:
        raise ValueError("observation.object_text is required")
    observation_id = "obs:" + _sha256_payload(
        {
            "run_id": payload["run"]["run_id"],
            "unit_id": unit_id,
            "predicate_key": predicate_key,
            "object_text": object_text,
            "order": len(payload["observations"]),
        }
    )[:16]
    payload["observations"].append(
        {
            "observation_id": observation_id,
            "statement_id": statement["statement_id"],
            "excerpt_id": excerpt["excerpt_id"],
            "source_id": source["source_id"],
            "observation_order": len([row for row in payload["observations"] if row["statement_id"] == statement["statement_id"]]) + 1,
            "predicate_key": predicate_key,
            "predicate_family": OBSERVATION_PREDICATE_TO_FAMILY[predicate_key],
            "object_text": object_text,
            "object_type": str(observation.get("object_type") or "note"),
            "object_ref": observation.get("object_ref"),
            "subject_text": observation.get("subject_text"),
            "observation_status": str(observation.get("observation_status") or "captured"),
            "provenance": {
                "source": "personal_handoff_input",
                "unit_id": unit_id,
                **(
                    {"signal_classes": [str(value) for value in observation.get("signal_classes", [])]}
                    if isinstance(observation.get("signal_classes"), list)
                    else {}
                ),
            },
        }
    )


def _append_review(payload: dict[str, Any], review: Mapping[str, Any], fact_index_by_unit_id: Mapping[str, int]) -> None:
    unit_id = str(review.get("unit_id") or "").strip()
    fact_index = fact_index_by_unit_id.get(unit_id)
    if fact_index is None:
        raise ValueError(f"review references unknown unit_id: {unit_id}")
    fact = payload["fact_candidates"][fact_index]
    review_status = str(review.get("review_status") or "").strip()
    if not review_status:
        raise ValueError("review.review_status is required")
    note = str(review.get("note") or "").strip()
    review_id = "review:" + _sha256_payload(
        {
            "run_id": payload["run"]["run_id"],
            "unit_id": unit_id,
            "fact_id": fact["fact_id"],
            "review_status": review_status,
            "note": note,
        }
    )[:16]
    payload["reviews"].append(
        {
            "review_id": review_id,
            "fact_id": fact["fact_id"],
            "review_status": review_status,
            "reviewer": "personal_handoff_builder",
            "note": note,
            "provenance": {"source": "personal_handoff_input", "unit_id": unit_id},
        }
    )


def build_personal_handoff_report(input_payload: Mapping[str, Any]) -> dict[str, Any]:
    source_label = str(input_payload.get("source_label") or "").strip()
    if not source_label:
        raise ValueError("source_label is required")
    notes = str(input_payload.get("notes") or "").strip() or None
    recipient_profile = _normalize_profile(str(input_payload.get("recipient_profile") or ""))
    handoff_flags = input_payload.get("handoff") if isinstance(input_payload.get("handoff"), Mapping) else {}
    protected_envelope = _build_protected_disclosure_envelope(handoff_flags)
    entries = list(input_payload.get("entries", [])) if isinstance(input_payload.get("entries"), list) else []
    units = _load_units(entries)
    entry_policies = _build_entry_policies(entries)
    fact_payload = build_fact_intake_payload_from_text_units(units, source_label=source_label, notes=notes)
    _set_source_signal_classes(fact_payload, entry_policies)
    statement_index_by_unit_id = _statement_index_by_unit_id(fact_payload)
    fact_index_by_unit_id = _fact_index_by_unit_id(fact_payload)
    for observation in input_payload.get("observations", []):
        if isinstance(observation, Mapping):
            _append_observation(fact_payload, observation, statement_index_by_unit_id)
    for review in input_payload.get("reviews", []):
        if isinstance(review, Mapping):
            _append_review(fact_payload, review, fact_index_by_unit_id)

    with sqlite3.connect(":memory:") as conn:
        conn.row_factory = sqlite3.Row
        persist_summary = persist_fact_intake_payload(conn, fact_payload)
        fact_report = build_fact_intake_report(conn, run_id=fact_payload["run"]["run_id"])
        review_summary = build_fact_review_run_summary(conn, run_id=fact_payload["run"]["run_id"])
        operator_views = build_fact_review_operator_views(conn, run_id=fact_payload["run"]["run_id"])

    statement_by_id = {str(row["statement_id"]): row for row in fact_report["statements"]}
    source_by_id = {str(row["source_id"]): row for row in fact_report["sources"]}
    queue_by_fact_id = {str(row["fact_id"]): row for row in review_summary["facts"]}
    profile = _RECIPIENT_PROFILES[recipient_profile]
    exported_items: list[dict[str, Any]] = []
    excluded_items: list[dict[str, Any]] = []
    for fact in fact_report["facts"]:
        statement_ids = [str(value) for value in fact.get("statement_ids", []) if str(value).strip()]
        unit_ids: list[str] = []
        policies: list[EntryPolicy] = []
        for statement_id in statement_ids:
            statement = statement_by_id.get(statement_id)
            if not statement:
                continue
            provenance = statement.get("provenance") if isinstance(statement.get("provenance"), Mapping) else {}
            unit_id = str(provenance.get("unit_id") or "").strip()
            if not unit_id:
                continue
            unit_ids.append(unit_id)
            policy = entry_policies.get(unit_id)
            if policy is not None:
                policies.append(policy)
        allowed = any(recipient_profile in policy.share_with for policy in policies) if policies else True
        strongest_policy = max((policy.text_export_policy for policy in policies), key=lambda value: _EXPORT_POLICY_ORDER[value], default="full")
        protected_only = any(policy.protected_disclosure_only for policy in policies)
        protected_reason = next((policy.protected_disclosure_reason for policy in policies if policy.protected_disclosure_reason), None)
        summary_row = queue_by_fact_id.get(str(fact["fact_id"]), {})
        base_row = {
            "fact_id": fact["fact_id"],
            "unit_ids": unit_ids,
            "label": fact["canonical_label"] or fact["fact_text"][:80],
            "candidate_status": fact["candidate_status"],
            "signal_classes": list(summary_row.get("signal_classes", [])),
            "source_signal_classes": list(summary_row.get("source_signal_classes", [])),
            "reason_codes": list(summary_row.get("reason_codes", [])),
            "latest_review_status": summary_row.get("latest_review_status"),
            "latest_review_note": summary_row.get("latest_review_note"),
            "source_types": list(summary_row.get("source_types", [])),
            "protected_disclosure_only": protected_only,
            "protected_disclosure_reason": protected_reason,
        }
        if protected_envelope.enabled and protected_only and recipient_profile not in protected_envelope.allowed_recipient_profiles:
            excluded_items.append(
                {
                    **base_row,
                    "exclusion_reason": "protected_disclosure_scope_mismatch",
                }
            )
            continue
        if not allowed:
            excluded_items.append({**base_row, "exclusion_reason": "recipient_not_permitted"})
            continue
        if strongest_policy == "omit":
            excluded_items.append({**base_row, "exclusion_reason": "text_export_policy_omit"})
            continue
        exported_items.append(
            {
                **base_row,
                "text_export_policy": strongest_policy,
                "export_text": "[REDACTED]" if strongest_policy == "redact" else fact["fact_text"],
                "text_redacted": strongest_policy == "redact",
                "source_refs": [
                    {
                        "source_id": source_id,
                        "source_type": (source_by_id.get(source_id) or {}).get("source_type"),
                        "source_label": (source_by_id.get(source_id) or {}).get("source_label"),
                    }
                    for source_id in fact.get("source_ids", [])
                    if source_id in source_by_id
                ],
            }
        )

    preferred_view_key = profile["preferred_operator_view"]
    preferred_view = operator_views[preferred_view_key]
    return {
        "version": PERSONAL_HANDOFF_REPORT_VERSION,
        "created_at": _created_at_utc(),
        "run": {
            "source_label": source_label,
            "fact_run_id": fact_payload["run"]["run_id"],
                "recipient_profile": recipient_profile,
                "recipient_title": profile["title"],
                "preferred_operator_view": preferred_view_key,
                "local_only": bool(handoff_flags.get("local_only")) or protected_envelope.enabled,
                "do_not_sync": bool(handoff_flags.get("do_not_sync")) or protected_envelope.enabled,
                "retention_policy": str(handoff_flags.get("retention_policy") or "personal_local_only_v1"),
                "redaction_policy": str(handoff_flags.get("redaction_policy") or "scoped_export_v1"),
            },
        "protected_disclosure": {
            "enabled": protected_envelope.enabled,
            "disclosure_level": protected_envelope.disclosure_level,
            "envelope_policy": protected_envelope.envelope_policy,
            "handling_notice": protected_envelope.handling_notice,
            "allowed_recipient_profiles": list(protected_envelope.allowed_recipient_profiles),
            "active_restrictions": (
                ["force_local_only", "force_do_not_sync", "protected_scope_filter"]
                if protected_envelope.enabled
                else []
            ),
        },
        "persist_summary": persist_summary,
        "fact_report": {
            "run": fact_report["run"],
            "summary": fact_report["summary"],
            "sources": fact_report["sources"],
            "statements": fact_report["statements"],
            "facts": fact_report["facts"],
            "observations": fact_report["observations"],
            "reviews": fact_report.get("reviews", []),
        },
        "review_summary": review_summary,
        "operator_views": operator_views,
        "recipient_export": {
            "recipient_profile": recipient_profile,
            "preferred_operator_view": {
                "key": preferred_view_key,
                "title": preferred_view["title"],
                "summary": preferred_view["summary"],
            },
            "exported_item_count": len(exported_items),
            "excluded_item_count": len(excluded_items),
            "items": exported_items,
            "excluded_items": excluded_items,
        },
    }


def render_personal_handoff_summary(report: Mapping[str, Any]) -> str:
    run = report.get("run") if isinstance(report.get("run"), Mapping) else {}
    recipient_export = report.get("recipient_export") if isinstance(report.get("recipient_export"), Mapping) else {}
    fact_report = report.get("fact_report") if isinstance(report.get("fact_report"), Mapping) else {}
    report_summary = fact_report.get("summary") if isinstance(fact_report.get("summary"), Mapping) else {}
    preferred_view = recipient_export.get("preferred_operator_view") if isinstance(recipient_export.get("preferred_operator_view"), Mapping) else {}
    protected_disclosure = report.get("protected_disclosure") if isinstance(report.get("protected_disclosure"), Mapping) else {}
    lines = [
        "# Personal handoff report",
        "",
        f"- Recipient profile: {run.get('recipient_profile')}",
        f"- Source label: {run.get('source_label')}",
        f"- Fact count: {report_summary.get('fact_count', 0)}",
        f"- Review queue count: {report_summary.get('review_queue_count', 0)}",
        f"- Exported items: {recipient_export.get('exported_item_count', 0)}",
        f"- Excluded items: {recipient_export.get('excluded_item_count', 0)}",
        f"- Preferred operator view: {preferred_view.get('key')}",
        "",
    ]
    if bool(protected_disclosure.get("enabled")):
        lines.extend(
            [
                "## Protected disclosure",
                "",
                f"- Disclosure level: {protected_disclosure.get('disclosure_level')}",
                f"- Envelope policy: {protected_disclosure.get('envelope_policy')}",
                f"- Handling notice: {protected_disclosure.get('handling_notice')}",
                f"- Allowed recipients: {', '.join(protected_disclosure.get('allowed_recipient_profiles', []))}",
                "",
            ]
        )
    lines.extend(
        [
        "## Exported items",
        "",
        ]
    )
    items = recipient_export.get("items") if isinstance(recipient_export.get("items"), list) else []
    if items:
        for item in items:
            label = str(item.get("label") or item.get("fact_id") or "")
            status = str(item.get("latest_review_status") or "unreviewed")
            policy = str(item.get("text_export_policy") or "full")
            lines.append(f"- {label} | review={status} | text_policy={policy}")
    else:
        lines.append("- No items were exportable for the selected recipient profile.")
    excluded = recipient_export.get("excluded_items") if isinstance(recipient_export.get("excluded_items"), list) else []
    lines.extend(["", "## Exclusions", ""])
    if excluded:
        for item in excluded:
            label = str(item.get("fact_id") or item.get("label") or "")
            reason = str(item.get("exclusion_reason") or "excluded")
            lines.append(f"- {label} | {reason}")
    else:
        lines.append("- No exclusions.")
    return "\n".join(lines) + "\n"
