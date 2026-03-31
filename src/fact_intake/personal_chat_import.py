from __future__ import annotations

import json
from typing import Any, Mapping

from src.reporting.structure_report import TextUnit

from .disclosure_policy import (
    DEFAULT_HANDOFF_SHARE_WITH,
    DEFAULT_PROTECTED_ALLOWED_RECIPIENT_PROFILES,
    normalize_profile,
)
from .personal_handoff_bundle import build_personal_handoff_report
from .protected_disclosure_envelope import build_protected_disclosure_envelope


def _render_message_text(message: Mapping[str, Any]) -> str:
    text = str(message.get("text") or "").strip()
    if not text:
        raise ValueError("messages require text")
    speaker = str(message.get("speaker") or "").strip()
    ts = str(message.get("ts") or "").strip()
    if speaker and ts:
        return f"[{ts}] {speaker}: {text}"
    if speaker:
        return f"{speaker}: {text}"
    if ts:
        return f"[{ts}] {text}"
    return text


def _build_envelope_summary(message: Mapping[str, Any]) -> str:
    explicit = str(message.get("envelope_summary") or "").strip()
    if explicit:
        return explicit
    speaker = str(message.get("speaker") or "participant").strip() or "participant"
    ts = str(message.get("ts") or "unknown time").strip() or "unknown time"
    return f"Chat message from {speaker} at {ts}"


def _normalize_messages_to_entries(input_payload: Mapping[str, Any], *, protected: bool) -> list[dict[str, Any]]:
    source_type_default = str(input_payload.get("source_type") or "chat_archive_sample").strip() or "chat_archive_sample"
    source_id_default = str(input_payload.get("source_id") or "chat_import").strip() or "chat_import"
    entries: list[dict[str, Any]] = []
    messages = input_payload.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ValueError("messages is required")
    for index, raw_message in enumerate(messages, start=1):
        if not isinstance(raw_message, Mapping):
            continue
        unit_id = str(raw_message.get("message_id") or f"msg:{index}").strip()
        if not unit_id:
            raise ValueError("message_id must not be blank")
        entry = {
            "unit_id": unit_id,
            "source_id": str(raw_message.get("source_id") or source_id_default).strip() or source_id_default,
            "source_type": str(raw_message.get("source_type") or source_type_default).strip() or source_type_default,
            "text": _render_message_text(raw_message),
            "share_with": raw_message.get("share_with"),
        }
        if protected:
            entry.update(
                {
                    "local_handle": str(raw_message.get("local_handle") or f"chat://{unit_id}").strip(),
                    "envelope_summary": _build_envelope_summary(raw_message),
                    "identity_policy": str(raw_message.get("identity_policy") or "withheld"),
                    "envelope_export_policy": str(raw_message.get("envelope_export_policy") or "metadata_only"),
                    "protected_disclosure_only": bool(raw_message.get("protected_disclosure_only")),
                }
            )
            protected_reason = str(raw_message.get("protected_disclosure_reason") or "").strip()
            if protected_reason:
                entry["protected_disclosure_reason"] = protected_reason
        else:
            entry["text_export_policy"] = str(raw_message.get("text_export_policy") or "full")
            if isinstance(raw_message.get("signal_classes"), list):
                entry["signal_classes"] = [str(value) for value in raw_message["signal_classes"]]
        entries.append(entry)
    return entries


def build_handoff_input_from_chat_json(input_payload: Mapping[str, Any]) -> dict[str, Any]:
    mode = str(input_payload.get("mode") or "personal_handoff").strip()
    protected = mode == "protected_disclosure_envelope"
    if mode not in {"personal_handoff", "protected_disclosure_envelope"}:
        raise ValueError(f"unsupported mode: {mode}")
    recipient_profile = normalize_profile(str(input_payload.get("recipient_profile") or ""))
    payload = {
        "mode": mode,
        "source_label": str(input_payload.get("source_label") or "").strip(),
        "notes": input_payload.get("notes"),
        "recipient_profile": recipient_profile,
        "handoff": dict(input_payload.get("handoff") or {}),
        "entries": _normalize_messages_to_entries(input_payload, protected=protected),
        "observations": list(input_payload.get("observations", [])) if isinstance(input_payload.get("observations"), list) else [],
        "reviews": list(input_payload.get("reviews", [])) if isinstance(input_payload.get("reviews"), list) else [],
    }
    if not payload["source_label"]:
        raise ValueError("source_label is required")
    return payload


def build_handoff_input_from_units(
    *,
    units: list[TextUnit],
    source_label: str,
    recipient_profile: str,
    mode: str = "personal_handoff",
    notes: str | None = None,
    handoff: Mapping[str, Any] | None = None,
    default_share_with: list[str] | None = None,
) -> dict[str, Any]:
    if not units:
        raise ValueError("units is required")
    if mode not in {"personal_handoff", "protected_disclosure_envelope"}:
        raise ValueError(f"unsupported mode: {mode}")
    protected = mode == "protected_disclosure_envelope"
    recipient_profile = normalize_profile(recipient_profile)
    share_with = list(default_share_with) if default_share_with else list(DEFAULT_HANDOFF_SHARE_WITH)
    messages: list[dict[str, Any]] = []
    for unit in units:
        message: dict[str, Any] = {
            "message_id": unit.unit_id,
            "text": unit.text,
            "share_with": share_with,
            "source_id": unit.source_id,
            "source_type": unit.source_type,
        }
        if protected:
            message["envelope_export_policy"] = "metadata_only"
            message["identity_policy"] = "withheld"
            message["local_handle"] = f"{unit.source_type}://{unit.unit_id}"
            message["envelope_summary"] = f"{unit.source_type} message {unit.unit_id}"
        else:
            message["text_export_policy"] = "full"
        messages.append(message)
    handoff_payload = dict(handoff or {})
    if protected and "protected_disclosure" not in handoff_payload:
        handoff_payload.update(
            {
                "mode": "protected_disclosure_envelope_v1",
                "export_boundary": "metadata_only",
                "retaliation_risk_level": "unspecified",
                "protected_disclosure": {
                    "enabled": True,
                    "disclosure_level": "protected_disclosure_v1",
                    "envelope_policy": "protected_disclosure_local_only_v1",
                    "handling_notice": "Protected-disclosure material must remain local-only and scoped to legal or regulatory recipients.",
                    "allowed_recipient_profiles": list(DEFAULT_PROTECTED_ALLOWED_RECIPIENT_PROFILES),
                },
            }
        )
    return build_handoff_input_from_chat_json(
        {
            "mode": mode,
            "source_label": source_label,
            "recipient_profile": recipient_profile,
            "notes": notes,
            "handoff": handoff_payload,
            "messages": messages,
        }
    )


def build_handoff_report_from_chat_json(input_payload: Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(input_payload.get("entries"), list):
        payload = dict(input_payload)
    else:
        payload = build_handoff_input_from_chat_json(input_payload)
    mode = str(input_payload.get("mode") or "personal_handoff").strip()
    if mode == "protected_disclosure_envelope":
        return build_protected_disclosure_envelope(payload)
    return build_personal_handoff_report(payload)


def render_chat_input_debug_payload(input_payload: Mapping[str, Any]) -> str:
    payload = build_handoff_input_from_chat_json(input_payload)
    return json.dumps(payload, indent=2, sort_keys=True)
