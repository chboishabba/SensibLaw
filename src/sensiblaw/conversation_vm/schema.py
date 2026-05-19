"""Schema constants and deterministic helpers for the Conversation VM."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

STATE_SCHEMA = "sl.conversation_vm_state.v0_1"
TURN_DELTA_SCHEMA = "sl.conversation_turn_delta.v0_1"
PROOF_SURFACE_SCHEMA = "sl.conversation_proof_surface.v0_1"
CONTEXT_PAYLOAD_SCHEMA = "sl.conversation_context_payload.v0_1"

STATUS_ORDER = (
    "candidate",
    "supported",
    "promoted",
    "contested",
    "blocked",
    "abstained",
    "retracted",
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def stable_id(prefix: str, value: Any) -> str:
    digest = hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()[:24]
    return f"{prefix}_{digest}"


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def receipt(kind: str, target_id: str, evidence_ids: list[str], payload: dict[str, Any]) -> dict[str, Any]:
    body = {
        "kind": kind,
        "target_id": target_id,
        "evidence_ids": sorted(evidence_ids),
        "payload": payload,
    }
    return {
        "id": stable_id("rcpt", body),
        **body,
    }
