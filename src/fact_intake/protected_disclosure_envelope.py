from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping

PROTECTED_DISCLOSURE_ENVELOPE_VERSION = "protected.disclosure.envelope.v1"

_RECIPIENT_PROFILES = {"lawyer", "doctor", "advocate", "regulator"}
_ENVELOPE_EXPORT_POLICIES = {"metadata_only", "redact", "omit"}
_IDENTITY_POLICIES = {"named", "pseudonymous", "withheld"}
_RETALIATION_RISK_LEVELS = {"unspecified", "low", "moderate", "high", "extreme"}
_DISCLOSURE_ROUTES = {
    "counsel_or_regulator_first",
    "regulator_only",
    "support_or_counsel_first",
    "care_or_counsel_first",
}
_MINIMIZATION_MODES = {
    "standard_metadata_only",
    "pseudonymous_or_withheld_only",
    "withheld_identity_only",
}
_RECIPIENT_CLASS_BY_PROFILE = {
    "lawyer": "legal_counsel",
    "regulator": "external_oversight",
    "advocate": "support_advocacy",
    "doctor": "care_support",
}
_ROUTE_ALLOWED_CLASSES = {
    "counsel_or_regulator_first": {"legal_counsel", "external_oversight"},
    "regulator_only": {"external_oversight"},
    "support_or_counsel_first": {"legal_counsel", "support_advocacy"},
    "care_or_counsel_first": {"legal_counsel", "care_support"},
}
_IDENTITY_EXPOSURE_ORDER = {"withheld": 0, "pseudonymous": 1, "named": 2}
_MINIMIZATION_MAX_EXPOSURE = {
    "standard_metadata_only": 2,
    "pseudonymous_or_withheld_only": 1,
    "withheld_identity_only": 0,
}


def _stable_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256_payload(payload: object) -> str:
    return hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()


def _created_at_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_profile(value: str) -> str:
    text = str(value or "").strip().casefold()
    if text not in _RECIPIENT_PROFILES:
        raise ValueError(f"unsupported recipient_profile: {value}")
    return text


def _require_protected_disclosure(handoff: Mapping[str, Any]) -> Mapping[str, Any]:
    protected = handoff.get("protected_disclosure")
    if not isinstance(protected, Mapping) or not bool(protected.get("enabled")):
        raise ValueError("protected_disclosure.enabled=true is required for protected disclosure envelopes")
    return protected


def _normalize_allowed_recipients(protected: Mapping[str, Any]) -> list[str]:
    raw = protected.get("allowed_recipient_profiles")
    if not isinstance(raw, list) or not raw:
        raise ValueError("protected_disclosure.allowed_recipient_profiles is required")
    out = [_normalize_profile(str(value)) for value in raw]
    if len(set(out)) != len(out):
        raise ValueError("protected_disclosure.allowed_recipient_profiles must not contain duplicates")
    return out


def _normalize_retaliation_risk_level(value: Any) -> str:
    level = str(value or "unspecified").strip().casefold()
    if level not in _RETALIATION_RISK_LEVELS:
        raise ValueError(f"unsupported retaliation_risk_level: {value}")
    return level


def _normalize_disclosure_route(protected: Mapping[str, Any]) -> str:
    route = str(protected.get("disclosure_route") or "counsel_or_regulator_first").strip().casefold()
    if route not in _DISCLOSURE_ROUTES:
        raise ValueError(f"unsupported disclosure_route: {route}")
    return route


def _normalize_minimization_mode(protected: Mapping[str, Any], retaliation_risk_level: str) -> str:
    explicit = str(protected.get("minimization_mode") or "").strip().casefold()
    if explicit:
        if explicit not in _MINIMIZATION_MODES:
            raise ValueError(f"unsupported minimization_mode: {explicit}")
        return explicit
    if retaliation_risk_level == "extreme":
        return "withheld_identity_only"
    return "standard_metadata_only"


def _normalize_envelope_export_policy(entry: Mapping[str, Any]) -> str:
    policy = str(entry.get("envelope_export_policy") or "metadata_only").strip().casefold()
    if policy not in _ENVELOPE_EXPORT_POLICIES:
        raise ValueError(f"unsupported envelope_export_policy: {policy}")
    return policy


def _normalize_identity_policy(entry: Mapping[str, Any]) -> str:
    policy = str(entry.get("identity_policy") or "withheld").strip().casefold()
    if policy not in _IDENTITY_POLICIES:
        raise ValueError(f"unsupported identity_policy: {policy}")
    return policy


def _normalize_share_with(entry: Mapping[str, Any]) -> list[str]:
    raw = entry.get("share_with")
    if not isinstance(raw, list) or not raw:
        return []
    out = [_normalize_profile(str(value)) for value in raw]
    if len(set(out)) != len(out):
        raise ValueError("entry.share_with must not contain duplicates")
    return out


def _normalize_retaliation_risk_tags(entry: Mapping[str, Any]) -> list[str]:
    raw = entry.get("retaliation_risk_tags")
    if not isinstance(raw, list):
        return []
    out = [str(value).strip() for value in raw if str(value).strip()]
    return sorted(dict.fromkeys(out))


def _build_sealed_item(
    *,
    entry: Mapping[str, Any],
    recipient_profile: str,
    allowed_recipient_profiles: list[str],
    disclosure_route: str,
    minimization_mode: str,
    source_label: str,
    run_id: str,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    unit_id = str(entry.get("unit_id") or "").strip()
    source_id = str(entry.get("source_id") or "").strip()
    source_type = str(entry.get("source_type") or "").strip()
    if not unit_id or not source_id or not source_type:
        raise ValueError("entries require unit_id, source_id, and source_type")
    local_handle = str(entry.get("local_handle") or "").strip()
    envelope_summary = str(entry.get("envelope_summary") or "").strip()
    if not local_handle or not envelope_summary:
        raise ValueError("protected envelope entries require local_handle and envelope_summary")
    share_with = _normalize_share_with(entry)
    export_policy = _normalize_envelope_export_policy(entry)
    identity_policy = _normalize_identity_policy(entry)
    retaliation_risk_tags = _normalize_retaliation_risk_tags(entry)
    protected_only = bool(entry.get("protected_disclosure_only"))
    protected_reason = str(entry.get("protected_disclosure_reason") or "").strip() or None
    recipient_class = _RECIPIENT_CLASS_BY_PROFILE[recipient_profile]
    item_id = "envitem:" + _sha256_payload(
        {
            "run_id": run_id,
            "unit_id": unit_id,
            "local_handle": local_handle,
            "source_type": source_type,
            "export_policy": export_policy,
        }
    )[:16]
    base_row = {
        "item_id": item_id,
        "unit_id": unit_id,
        "local_handle": local_handle,
        "source_id": source_id,
        "source_type": source_type,
        "source_label": source_label,
        "identity_policy": identity_policy,
        "envelope_summary": envelope_summary,
        "share_with": share_with,
        "recipient_class": recipient_class,
        "export_policy": export_policy,
        "retaliation_risk_tags": retaliation_risk_tags,
        "protected_disclosure_only": protected_only,
        "protected_disclosure_reason": protected_reason,
    }
    if not share_with:
        return None, {**base_row, "exclusion_reason": "recipient_not_permitted"}
    if recipient_class not in _ROUTE_ALLOWED_CLASSES[disclosure_route]:
        return None, {**base_row, "exclusion_reason": "disclosure_route_mismatch"}
    if protected_only and recipient_profile not in allowed_recipient_profiles:
        return None, {**base_row, "exclusion_reason": "protected_disclosure_scope_mismatch"}
    if recipient_profile not in share_with:
        return None, {**base_row, "exclusion_reason": "recipient_not_permitted"}
    if export_policy == "omit":
        return None, {**base_row, "exclusion_reason": "envelope_export_policy_omit"}
    if _IDENTITY_EXPOSURE_ORDER[identity_policy] > _MINIMIZATION_MAX_EXPOSURE[minimization_mode]:
        return None, {**base_row, "exclusion_reason": "identity_policy_too_exposed"}
    return base_row, None


def build_protected_disclosure_envelope(input_payload: Mapping[str, Any]) -> dict[str, Any]:
    source_label = str(input_payload.get("source_label") or "").strip()
    if not source_label:
        raise ValueError("source_label is required")
    recipient_profile = _normalize_profile(str(input_payload.get("recipient_profile") or ""))
    notes = str(input_payload.get("notes") or "").strip() or None
    handoff = input_payload.get("handoff") if isinstance(input_payload.get("handoff"), Mapping) else {}
    protected = _require_protected_disclosure(handoff)
    allowed_recipient_profiles = _normalize_allowed_recipients(protected)
    retaliation_risk_level = _normalize_retaliation_risk_level(handoff.get("retaliation_risk_level"))
    disclosure_route = _normalize_disclosure_route(protected)
    minimization_mode = _normalize_minimization_mode(protected, retaliation_risk_level)
    run_id = "pdoenv:" + _sha256_payload(
        {
            "source_label": source_label,
            "recipient_profile": recipient_profile,
            "unit_ids": [str(entry.get("unit_id") or "").strip() for entry in input_payload.get("entries", [])],
            "local_case_ref": str(handoff.get("local_case_ref") or ""),
        }
    )[:16]

    sealed_items: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    for raw_entry in input_payload.get("entries", []):
        if not isinstance(raw_entry, Mapping):
            continue
        item, exclusion = _build_sealed_item(
            entry=raw_entry,
            recipient_profile=recipient_profile,
            allowed_recipient_profiles=allowed_recipient_profiles,
            disclosure_route=disclosure_route,
            minimization_mode=minimization_mode,
            source_label=source_label,
            run_id=run_id,
        )
        if item is not None:
            sealed_items.append(item)
        if exclusion is not None:
            exclusions.append(exclusion)

    observation_markers: list[dict[str, Any]] = []
    for raw_observation in input_payload.get("observations", []):
        if not isinstance(raw_observation, Mapping):
            continue
        observation_markers.append(
            {
                "unit_id": str(raw_observation.get("unit_id") or "").strip(),
                "predicate_key": str(raw_observation.get("predicate_key") or "").strip(),
                "object_type": str(raw_observation.get("object_type") or "note"),
                "observation_status": str(raw_observation.get("observation_status") or "captured"),
                "has_object_text": bool(str(raw_observation.get("object_text") or "").strip()),
            }
        )

    review_markers: list[dict[str, Any]] = []
    for raw_review in input_payload.get("reviews", []):
        if not isinstance(raw_review, Mapping):
            continue
        review_markers.append(
            {
                "unit_id": str(raw_review.get("unit_id") or "").strip(),
                "review_status": str(raw_review.get("review_status") or "").strip(),
                "has_note": bool(str(raw_review.get("note") or "").strip()),
            }
        )

    return {
        "version": PROTECTED_DISCLOSURE_ENVELOPE_VERSION,
        "created_at": _created_at_utc(),
        "run": {
            "envelope_id": run_id,
            "source_label": source_label,
            "recipient_profile": recipient_profile,
            "notes_present": notes is not None,
            "mode": str(handoff.get("mode") or "protected_disclosure_envelope_v1"),
            "export_boundary": str(handoff.get("export_boundary") or "metadata_only"),
            "retaliation_risk_level": retaliation_risk_level,
            "local_case_ref": str(handoff.get("local_case_ref") or ""),
            "local_only": True,
            "do_not_sync": True,
        },
        "protected_disclosure": {
            "enabled": True,
            "disclosure_level": str(protected.get("disclosure_level") or "protected_disclosure_v1"),
            "envelope_policy": str(protected.get("envelope_policy") or "protected_disclosure_local_only_v1"),
            "disclosure_route": disclosure_route,
            "minimization_mode": minimization_mode,
            "handling_notice": str(
                protected.get("handling_notice")
                or "Protected-disclosure material must remain local-only and do-not-sync."
            ),
            "allowed_recipient_profiles": allowed_recipient_profiles,
            "active_restrictions": [
                "force_local_only",
                "force_do_not_sync",
                "metadata_only_export",
                "deny_by_default",
                f"route:{disclosure_route}",
                f"minimization:{minimization_mode}",
            ],
        },
        "sealed_items": sealed_items,
        "exclusions": exclusions,
        "observation_markers": observation_markers,
        "review_markers": review_markers,
        "integrity": {
            "input_entry_count": len([row for row in input_payload.get("entries", []) if isinstance(row, Mapping)]),
            "sealed_item_count": len(sealed_items),
            "exclusion_count": len(exclusions),
            "observation_marker_count": len(observation_markers),
            "review_marker_count": len(review_markers),
        },
    }


def render_protected_disclosure_summary(report: Mapping[str, Any]) -> str:
    run = report.get("run") if isinstance(report.get("run"), Mapping) else {}
    protected = report.get("protected_disclosure") if isinstance(report.get("protected_disclosure"), Mapping) else {}
    integrity = report.get("integrity") if isinstance(report.get("integrity"), Mapping) else {}
    lines = [
        "# Protected disclosure envelope",
        "",
        f"- Recipient profile: {run.get('recipient_profile')}",
        f"- Source label: {run.get('source_label')}",
        f"- Export boundary: {run.get('export_boundary')}",
        f"- Retaliation risk level: {run.get('retaliation_risk_level')}",
        f"- Local only: {run.get('local_only')}",
        f"- Do not sync: {run.get('do_not_sync')}",
        "",
        "## Envelope",
        "",
        f"- Disclosure level: {protected.get('disclosure_level')}",
        f"- Envelope policy: {protected.get('envelope_policy')}",
        f"- Disclosure route: {protected.get('disclosure_route')}",
        f"- Minimization mode: {protected.get('minimization_mode')}",
        f"- Handling notice: {protected.get('handling_notice')}",
        f"- Allowed recipients: {', '.join(protected.get('allowed_recipient_profiles', []))}",
        "",
        "## Counts",
        "",
        f"- Sealed items: {integrity.get('sealed_item_count', 0)}",
        f"- Exclusions: {integrity.get('exclusion_count', 0)}",
        f"- Observation markers: {integrity.get('observation_marker_count', 0)}",
        f"- Review markers: {integrity.get('review_marker_count', 0)}",
        "",
        "## Sealed items",
        "",
    ]
    items = report.get("sealed_items") if isinstance(report.get("sealed_items"), list) else []
    if items:
        for item in items:
            lines.append(
                f"- {item.get('item_id')} | handle={item.get('local_handle')} | summary={item.get('envelope_summary')} | export_policy={item.get('export_policy')}"
            )
    else:
        lines.append("- No sealed items were exportable for the selected recipient.")
    exclusions = report.get("exclusions") if isinstance(report.get("exclusions"), list) else []
    lines.extend(["", "## Exclusions", ""])
    if exclusions:
        for item in exclusions:
            lines.append(
                f"- {item.get('item_id')} | handle={item.get('local_handle')} | reason={item.get('exclusion_reason')}"
            )
    else:
        lines.append("- No exclusions.")
    return "\n".join(lines) + "\n"
