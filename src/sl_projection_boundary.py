"""Projection boundary helpers for Observation/Claim contracts to RDF/Wikidata exports."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

SL_WIKIDATA_PROJECTION_VERSION = "sl.observation_claim.wikidata_projection.v1"
SL_OBSERVATION_CLAIM_CONTRACT_VERSION = "sl.observation_claim.contract.v1"


def _required_str(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} is required and must be a non-empty string")
    return value.strip()


def _optional_str(payload: Mapping[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string when present")
    value = value.strip()
    return value or None


def _optional_timestamp(payload: Mapping[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty ISO-8601 string when present")

    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{key} must be a valid ISO-8601 timestamp") from exc

    return value.strip()


def _parse_iso8601(payload: Mapping[str, Any], key: str) -> datetime:
    value = _required_str(payload, key)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{key} must be a valid ISO-8601 timestamp") from exc


def _as_list(payload: Mapping[str, Any], key: str) -> list[Any]:
    value = payload.get(key, [])
    if not isinstance(value, list):
        raise ValueError(f"{key} must be an array")
    return value


def _coerce_posture_to_wikidata(posture: str) -> str:
    match posture:
        case "asserted":
            return "supported"
        case "denied":
            return "contradicted"
        case "abstained":
            return "abstained"
        case _:
            return "unknown"


def _legal_norm_from_version(legal_version: str) -> str:
    return legal_version.split(":", 1)[0].strip() or legal_version


def _jurisdiction_tokens(jurisdiction: str) -> tuple[str, ...]:
    tokens = []
    token = []
    for char in jurisdiction:
        if char in {"_", "/", "-", ":"}:
            if token:
                tokens.append("".join(token).strip().upper())
                token = []
        else:
            token.append(char)
    if token:
        tokens.append("".join(token).strip().upper())
    return tuple(tokens)


def _jurisdiction_compatible(parent: str, child: str) -> bool:
    parent_tokens = _jurisdiction_tokens(parent)
    child_tokens = _jurisdiction_tokens(child)
    return parent_tokens == child_tokens[: len(parent_tokens)]


def _transition_receipt_matches_claim_context(
    claim_jurisdiction: str | None,
    claim_norm_id: str | None,
    transition_receipt: Mapping[str, Any],
    claim_id: str,
) -> None:
    receipt_jurisdiction = _required_str(transition_receipt, "jurisdiction")
    if claim_jurisdiction and not (
        _jurisdiction_compatible(claim_jurisdiction, receipt_jurisdiction)
        or _jurisdiction_compatible(receipt_jurisdiction, claim_jurisdiction)
    ):
        raise ValueError(
            f"claim {claim_id} and transition receipt "
            f"{_required_str(transition_receipt, 'transition_receipt_id')} have mismatched jurisdictions"
        )

    transition_legal_version = _required_str(transition_receipt, "legal_version")
    if claim_norm_id:
        claim_norm_id = claim_norm_id.strip()
        legal_norm = _legal_norm_from_version(transition_legal_version)
        if claim_norm_id != legal_norm and claim_norm_id != transition_legal_version:
            raise ValueError(
                f"claim {claim_id} legal norm {claim_norm_id} is inconsistent with transition receipt "
                f"{_required_str(transition_receipt, 'transition_receipt_id')} legal_version {transition_legal_version}"
            )


def _evidence_refs_for_observation(observation: Mapping[str, Any]) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    evidence_refs = observation.get("evidence_refs", [])
    if not isinstance(evidence_refs, list):
        raise ValueError("observation.evidence_refs must be an array")
    for item in evidence_refs:
        if not isinstance(item, Mapping):
            raise ValueError("evidence_refs entries must be objects")
        span_ref = item.get("span_ref")
        ref_type = item.get("ref_type")
        if not isinstance(span_ref, str) or not span_ref.strip():
            raise ValueError("evidence_refs.span_ref is required and must be non-empty")
        if not isinstance(ref_type, str) or not ref_type.strip():
            raise ValueError("evidence_refs.ref_type is required and must be non-empty")
        refs.append({"ref_type": ref_type.strip(), "ref_value": span_ref.strip()})
    return refs


def _load_evidence_links(payload: Mapping[str, Any]) -> dict[str, Any]:
    links_by_id: dict[str, Any] = {}
    for link in _as_list(payload, "evidence_links"):
        if not isinstance(link, Mapping):
            raise ValueError("evidence_links entries must be objects")
        link_id = _required_str(link, "link_id")
        links_by_id[link_id] = link
    return links_by_id


def _load_observations(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    observations_by_id: dict[str, Mapping[str, Any]] = {}
    for observation in _as_list(payload, "observations"):
        if not isinstance(observation, Mapping):
            raise ValueError("observations entries must be objects")
        observation_id = _required_str(observation, "observation_id")
        observations_by_id[observation_id] = observation
    return observations_by_id


def _load_transition_receipts(
    payload: Mapping[str, Any],
    evidence_links_by_id: Mapping[str, Mapping[str, Any]],
    valid_observation_ids: set[str],
) -> tuple[dict[str, list[str]], dict[str, Mapping[str, Any]], int, int, int]:
    transitions_by_observation: dict[str, list[tuple[str, datetime, datetime | None]]] = {}
    transition_receipts_by_id: dict[str, Mapping[str, Any]] = {}
    transition_receipt_count = 0
    legal_version_count = 0
    jurisdiction_count = 0
    seen_receipt_ids: set[str] = set()

    transition_receipts: list[Any] = []
    transition_receipts.extend(_as_list(payload, "transition_receipts"))
    for link_id, link in evidence_links_by_id.items():
        for receipt in _as_list(link, "transition_receipts"):
            transition_receipts.append(receipt)

    for receipt in transition_receipts:
        if not isinstance(receipt, Mapping):
            raise ValueError("transition_receipts entries must be objects")

        receipt_id = _required_str(receipt, "transition_receipt_id")
        if receipt_id in seen_receipt_ids:
            continue
        _required_str(receipt, "current_state")
        _required_str(receipt, "next_state")
        _required_str(receipt, "rule_id")
        _required_str(receipt, "rule_version")
        _required_str(receipt, "jurisdiction")
        _required_str(receipt, "legal_version")
        effective_from_dt = _parse_iso8601(receipt, "effective_from")
        effective_to = receipt.get("effective_to")
        if effective_to is not None:
            effective_to_dt = _optional_timestamp(receipt, "effective_to")
            if effective_to_dt is None:
                raise ValueError("effective_to must be a valid ISO-8601 timestamp when present")
            effective_to_dt = datetime.fromisoformat(effective_to_dt.replace("Z", "+00:00"))
            if effective_to_dt < effective_from_dt:
                raise ValueError(
                    "transition_receipts.effective_to must be greater than or equal to effective_from"
                )
            window_end = effective_to_dt
        else:
            window_end = None
        if _optional_str(receipt, "legal_version") is not None:
            legal_version_count += 1
        if _optional_str(receipt, "jurisdiction") is not None:
            jurisdiction_count += 1

        deltas = _as_list(receipt, "deltas")
        for delta in deltas:
            if not isinstance(delta, Mapping):
                raise ValueError("transition_receipts.deltas entries must be objects")
            _required_str(delta, "kind")
            _required_str(delta, "before")
            _required_str(delta, "after")

        for raw_observation_id in _as_list(receipt, "observation_ids"):
            if not isinstance(raw_observation_id, str) or not raw_observation_id.strip():
                raise ValueError("transition_receipts.observation_ids must contain non-empty strings")
            observation_id = raw_observation_id.strip()
            if observation_id not in valid_observation_ids:
                raise ValueError(f"transition_receipts.observation_ids references unknown observation {observation_id}")
            transitions_by_observation.setdefault(observation_id, []).append(
                (receipt_id, effective_from_dt, window_end)
            )

        transition_receipts_by_id[receipt_id] = receipt

        transition_receipt_count += 1
        seen_receipt_ids.add(receipt_id)

    for observation_id, scoped_receipts in transitions_by_observation.items():
        ordered = sorted(scoped_receipts, key=lambda row: (row[1], row[0]))
        active_until: datetime | None = None
        has_open_window = False
        for _, effective_from, effective_to in ordered:
            if has_open_window:
                raise ValueError(
                    f"transition_receipts temporal windows for {observation_id} must be non-overlapping"
                )
            if active_until is not None and effective_from < active_until:
                raise ValueError(
                    f"transition_receipts temporal windows for {observation_id} must be non-overlapping"
                )
            if effective_to is not None:
                active_until = effective_to
            else:
                has_open_window = True

        transitions_by_observation[observation_id] = ordered

    return (
        {
            observation_id: [receipt_id for receipt_id, _, _ in scoped_receipts]
            for observation_id, scoped_receipts in transitions_by_observation.items()
        },
        transition_receipts_by_id,
        transition_receipt_count,
        legal_version_count,
        jurisdiction_count,
    )


def build_wikidata_projection_report(payload: Mapping[str, Any]) -> dict[str, Any]:
    payload_version = _required_str(payload, "payload_version")
    if payload_version != SL_OBSERVATION_CLAIM_CONTRACT_VERSION:
        raise ValueError(f"payload_version must be {SL_OBSERVATION_CLAIM_CONTRACT_VERSION}")

    observations_by_id = _load_observations(payload)
    evidence_links_by_id = _load_evidence_links(payload)
    (
        transitions_by_observation,
        transition_receipts_by_id,
        transition_receipt_count,
        legal_version_count,
        jurisdiction_count,
    ) = _load_transition_receipts(payload, evidence_links_by_id, set(observations_by_id))
    recorded_jurisdictions: set[str] = set()
    temporal_scope_count = 0

    records: list[dict[str, Any]] = []
    dropped_fields = {"claim_id", "claim_created_at", "claim_updated_at", "hash", "source_conflict_refs", "evidence_conflicts"}

    for claim in _as_list(payload, "claims"):
        if not isinstance(claim, Mapping):
            raise ValueError("claims entries must be objects")
        claim_id = _required_str(claim, "claim_id")
        posture = _required_str(claim, "posture")
        observation_id = _required_str(claim, "observation_id")
        predicate = _required_str(claim, "predicate")
        subject_id = _required_str(claim, "subject_id")
        object_id = _required_str(claim, "object_id")
        subject_type = _required_str(claim, "subject_type")
        object_type = _required_str(claim, "object_type")

        observation = observations_by_id.get(observation_id)
        if observation is None:
            raise ValueError(f"claim {claim_id} references missing observation {observation_id}")

        jurisdiction = None
        claim_jurisdiction = claim.get("jurisdiction")
        if isinstance(claim_jurisdiction, str) and claim_jurisdiction.strip():
            jurisdiction = claim_jurisdiction.strip()
            recorded_jurisdictions.add(jurisdiction)
        else:
            observation_jurisdiction = observation.get("jurisdiction")
            if isinstance(observation_jurisdiction, str) and observation_jurisdiction.strip():
                jurisdiction = observation_jurisdiction.strip()
                recorded_jurisdictions.add(jurisdiction)

        observed_at = observation.get("observed_at")
        claim_updated_at = claim.get("claim_updated_at")
        effective_to = None
        if claim_updated_at is not None and observation.get("status") != "active":
            effective_to = claim_updated_at
        if observed_at is not None or claim.get("claim_created_at") is not None:
            temporal_scope_count += 1

        evidence_refs: list[dict[str, str]] = []
        evidence_refs.extend(_evidence_refs_for_observation(observation))
        evidence_link_ids = []
        for evidence_link_id in claim.get("evidence_links", []):
            if not isinstance(evidence_link_id, str) or not evidence_link_id.strip():
                raise ValueError("claim.evidence_links must contain non-empty strings")
            evidence_link_id = evidence_link_id.strip()
            evidence_link_ids.append(evidence_link_id)
            link = evidence_links_by_id.get(evidence_link_id)
            if link is None:
                continue
            trace_refs = link.get("trace_refs", [])
            if not isinstance(trace_refs, list):
                raise ValueError("evidence_links.trace_refs must be an array if present")
            for trace_ref in trace_refs:
                if not isinstance(trace_ref, str) or not trace_ref.strip():
                    raise ValueError("evidence_links.trace_refs entries must be non-empty strings")
                evidence_refs.append({"ref_type": "trace_ref", "ref_value": trace_ref.strip()})

        transition_receipt_ids = transitions_by_observation.get(observation_id, [])
        transition_receipts_payload = []
        for receipt_id in transition_receipt_ids:
            receipt = transition_receipts_by_id[receipt_id]
            _transition_receipt_matches_claim_context(jurisdiction, claim.get("norm_id"), receipt, claim_id)
            transition_receipts_payload.append(
                {
                    "transition_receipt_id": receipt_id,
                    "jurisdiction": _required_str(receipt, "jurisdiction"),
                    "legal_version": _required_str(receipt, "legal_version"),
                    "effective_from": _required_str(receipt, "effective_from"),
                    "effective_to": receipt.get("effective_to"),
                    "rule_version": _required_str(receipt, "rule_version"),
                }
            )

        records.append(
            {
                "projection_id": f"wdp:{claim_id}",
                "claim_id": claim_id,
                "observation_id": observation_id,
                "subject_id": subject_id,
                "subject_type": subject_type,
                "predicate": predicate,
                "object_id": object_id,
                "object_type": object_type,
                "wikidata_epistemic_value": _coerce_posture_to_wikidata(posture),
                "confidence": claim.get("confidence", None),
                "source_unit_id": _required_str(observation, "source_unit_id"),
                "norm_id": claim.get("norm_id"),
                "source_quote": observation.get("source_quote", None),
                "evidence_link_ids": evidence_link_ids,
                "evidence_refs": evidence_refs,
                "state_transition_receipt_ids": transitions_by_observation.get(observation_id, []),
                "state_transition_receipts": transition_receipts_payload,
                "temporal_scope": {
                    "observed_at": observation.get("observed_at"),
                    "asserted_at": claim.get("claim_created_at"),
                    "effective_from": claim.get("claim_created_at"),
                    "effective_to": effective_to,
                },
                "provenance": {
                    "jurisdiction": jurisdiction,
                    "observation_status": _required_str(observation, "status"),
                    "canonicality": _required_str(observation, "canonicality"),
                },
            }
        )

    return {
        "schema_version": SL_WIKIDATA_PROJECTION_VERSION,
        "source_contract_version": SL_OBSERVATION_CLAIM_CONTRACT_VERSION,
        "projection_mode": "evidence_preserving_reified_triples",
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "projection_records": records,
        "projection_summary": {
            "total_records": len(records),
            "dropped_field_count": len(dropped_fields),
            "jurisdiction_count": len(recorded_jurisdictions),
            "temporal_scope_records": temporal_scope_count,
            "transition_receipt_count": transition_receipt_count,
            "transition_receipts_with_jurisdiction": jurisdiction_count,
            "transition_receipts_with_legal_version": legal_version_count,
        },
    }
