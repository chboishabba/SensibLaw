from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Mapping, Sequence


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value).strip()


def _normalize_json_like(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            _stringify(key): _normalize_json_like(item)
            for key, item in sorted(value.items(), key=lambda item: _stringify(item[0]))
        }
    if isinstance(value, set):
        return [_normalize_json_like(item) for item in sorted(value, key=_stringify)]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_normalize_json_like(item) for item in value]
    if value is None:
        return None
    if isinstance(value, (bool, int, float, str)):
        return value
    return _stringify(value)


def _canonicalize_literal(value: Any) -> str:
    if isinstance(value, Mapping):
        return json.dumps(
            _normalize_json_like(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    if isinstance(value, set):
        return json.dumps(
            _normalize_json_like(value),
            ensure_ascii=False,
            separators=(",", ":"),
        )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return json.dumps(
            _normalize_json_like(value),
            ensure_ascii=False,
            separators=(",", ":"),
        )
    return _stringify(value)


def _anchor(anchor_kind: str, anchor_value: Any) -> dict[str, str] | None:
    value = _canonicalize_literal(anchor_value)
    if not value:
        return None
    return {
        "anchor_kind": anchor_kind,
        "anchor_value": value,
        "anchor_label": value,
    }


def _build_candidate_anchors(candidate: Mapping[str, Any]) -> list[dict[str, str]]:
    anchors: list[dict[str, str]] = []

    for anchor_kind, raw_value in (
        ("classification", candidate.get("classification")),
        ("review_action", candidate.get("action")),
        ("review_pressure", candidate.get("pressure")),
    ):
        anchor = _anchor(anchor_kind, raw_value)
        if anchor:
            anchors.append(anchor)

    for reason in candidate.get("reasons", []) or []:
        anchor = _anchor("review_reason", reason)
        if anchor:
            anchors.append(anchor)

    for evidence_ref in candidate.get("text_evidence_refs", []) or []:
        anchor = _anchor("text_evidence_ref", evidence_ref)
        if anchor:
            anchors.append(anchor)

    return anchors


def _render_candidate_text(candidate: Mapping[str, Any], claim_bundle: Mapping[str, Any]) -> str:
    subject = _canonicalize_literal(claim_bundle.get("subject"))
    predicate = _canonicalize_literal(claim_bundle.get("property"))
    obj = _canonicalize_literal(claim_bundle.get("value"))
    classification = _stringify(candidate.get("classification"))
    action = _stringify(candidate.get("action"))
    parts = [part for part in (subject, predicate, obj) if part]
    rendered = " ".join(parts)
    if classification or action:
        suffix = " ".join(part for part in (classification, action) if part)
        rendered = f"{rendered} [{suffix}]".strip()
    return rendered


def build_wikidata_relation_rows(
    migration_pack: Mapping[str, Any],
    *,
    source_family: str = "wikidata_migration_pack",
    source_kind: str = "wikidata_candidate_bundle",
) -> list[dict[str, Any]]:
    candidates = migration_pack.get("candidates")
    if not isinstance(candidates, Sequence) or isinstance(candidates, (str, bytes, bytearray)):
        raise ValueError("migration pack candidates must be a list")

    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            raise ValueError("migration pack candidates must be objects")
        candidate_id = _stringify(candidate.get("candidate_id"))
        if not candidate_id:
            raise ValueError("candidate requires candidate_id")
        claim_bundle = candidate.get("claim_bundle_before")
        if not isinstance(claim_bundle, Mapping):
            raise ValueError("candidate requires claim_bundle_before")

        actor = _canonicalize_literal(claim_bundle.get("subject"))
        action = _canonicalize_literal(claim_bundle.get("property"))
        obj = _canonicalize_literal(claim_bundle.get("value"))
        row = {
            "source_row_id": candidate_id,
            "source_id": f"wikidata_migration_pack:{candidate_id}",
            "event_id": f"wikidata_relation:{candidate_id}",
            "source_family": source_family,
            "source_kind": source_kind,
            "text": _render_candidate_text(candidate, claim_bundle),
            "actor": actor,
            "action": action,
            "object": obj,
            "candidate_anchors": _build_candidate_anchors(candidate),
            "provenance": {
                "candidate_id": candidate_id,
                "entity_qid": _stringify(candidate.get("entity_qid")),
                "slot_id": _stringify(candidate.get("slot_id")),
                "statement_index": candidate.get("statement_index"),
                "source_property": _stringify(migration_pack.get("source_property")),
                "target_property": _stringify(migration_pack.get("target_property")),
                "window_basis": deepcopy(migration_pack.get("window_basis")),
            },
            "structured_candidate": {
                "claim_bundle_before": deepcopy(claim_bundle),
                "claim_bundle_after": deepcopy(candidate.get("claim_bundle_after", {})),
                "qualifier_diff": deepcopy(candidate.get("qualifier_diff")),
                "reference_diff": deepcopy(candidate.get("reference_diff")),
            },
        }
        rows.append(row)
    return rows


__all__ = ["build_wikidata_relation_rows"]
