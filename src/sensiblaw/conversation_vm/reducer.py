"""Monotone join reducer for Conversation VM state."""

from __future__ import annotations

from copy import deepcopy
import json
import time
from typing import Any

from .schema import STATE_SCHEMA, stable_id

COLLECTIONS = (
    "sources",
    "excerpts",
    "statements",
    "observations",
    "predicate_atoms",
    "predicate_pnfs",
    "pnf_emission_receipts",
    "pnf_residual_receipts",
    "residual_comparisons",
    "promotion_gates",
    "proof_obligations",
    "blockers",
    "abstentions",
    "contested_items",
)


def empty_state() -> dict[str, Any]:
    return {
        "schema": STATE_SCHEMA,
        "id": stable_id("vm", {"schema": STATE_SCHEMA}),
        "version": "0.1",
        "applied_delta_ids": [],
        "status_history": [],
        **{name: [] for name in COLLECTIONS},
        "compact_payload_metadata": {},
    }


def step_state(state: dict[str, Any] | None, delta: dict[str, Any], metrics_callback: Any | None = None) -> dict[str, Any]:
    with _MetricSpan(metrics_callback, "copy", delta_id=delta.get("id")):
        next_state = _copy_state_for_update(state) if state else empty_state()
    delta_id = delta["id"]
    if delta_id in next_state["applied_delta_ids"]:
        return next_state

    with _MetricSpan(metrics_callback, "index_build", delta_id=delta_id):
        id_indexes = {
            name: {str(item.get("id")): item for item in next_state[name] if item.get("id")}
            for name in COLLECTIONS
        }
    touched_atom_ids = {str(item.get("id")) for item in delta.get("predicate_atoms", []) if item.get("id")}
    with _MetricSpan(metrics_callback, "join", delta_id=delta_id):
        for name in COLLECTIONS:
            for item in delta.get(name, []):
                _join_item(next_state[name], item, next_state["status_history"], delta_id, id_indexes[name])

    with _MetricSpan(metrics_callback, "cross_residual_derivation", delta_id=delta_id, touched_atom_count=len(touched_atom_ids)):
        _derive_cross_atom_residuals(next_state, delta_id, touched_atom_ids=touched_atom_ids)
    with _MetricSpan(metrics_callback, "pnf_residual_receipt_derivation", delta_id=delta_id):
        _derive_pnf_residual_receipts(next_state, delta_id)
    with _MetricSpan(metrics_callback, "contested_derivation", delta_id=delta_id):
        _derive_contested_items(next_state, delta_id)
    with _MetricSpan(metrics_callback, "blocked_derivation", delta_id=delta_id):
        _derive_blocked_promotions(next_state, delta_id)
    next_state["applied_delta_ids"].append(delta_id)
    next_state["applied_delta_ids"].sort()
    with _MetricSpan(metrics_callback, "metadata_update", delta_id=delta_id):
        next_state["compact_payload_metadata"] = {
            "delta_count": len(next_state["applied_delta_ids"]),
            "source_count": len(next_state["sources"]),
            "atom_count": len(next_state["predicate_atoms"]),
            "contested_count": len(next_state["contested_items"]),
            "abstention_count": len(next_state["abstentions"]),
        }
    return next_state


def _copy_state_for_update(state: dict[str, Any]) -> dict[str, Any]:
    copied = {key: value for key, value in state.items() if key not in COLLECTIONS}
    for name in COLLECTIONS:
        copied[name] = [dict(item) for item in state.get(name, [])]
    copied["applied_delta_ids"] = list(state.get("applied_delta_ids", []))
    copied["status_history"] = [dict(item) for item in state.get("status_history", [])]
    copied["compact_payload_metadata"] = dict(state.get("compact_payload_metadata") or {})
    return copied


def _join_item(
    collection: list[dict[str, Any]],
    item: dict[str, Any],
    history: list[dict[str, Any]],
    delta_id: str,
    id_index: dict[str, dict[str, Any]] | None = None,
) -> None:
    item_id = item.get("id")
    existing = id_index.get(str(item_id)) if id_index is not None and item_id else None
    if existing is None and id_index is None:
        existing = next((candidate for candidate in collection if candidate.get("id") == item_id), None)
    if existing is None:
        collection.append(deepcopy(item))
        if id_index is not None and item_id:
            id_index[str(item_id)] = collection[-1]
        if item.get("status"):
            history.append(_history(item["id"], None, item["status"], delta_id, item.get("receipt_ids", [])))
        collection.sort(key=lambda value: value.get("id", ""))
        return

    previous_status = existing.get("status")
    existing_receipts = set(existing.get("receipt_ids", []))
    incoming_receipts = set(item.get("receipt_ids", []))
    for key, value in item.items():
        if key == "receipt_ids":
            existing[key] = sorted(existing_receipts | incoming_receipts)
        elif key == "status":
            if value != previous_status:
                existing[key] = value
        elif key not in existing or existing[key] in (None, "", [], {}):
            existing[key] = deepcopy(value)
    if existing.get("status") != previous_status:
        history.append(
            _history(
                existing["id"],
                previous_status,
                existing.get("status"),
                delta_id,
                sorted(existing_receipts | incoming_receipts),
            )
        )


def _derive_contested_items(state: dict[str, Any], delta_id: str) -> None:
    atom_by_id = {atom["id"]: atom for atom in state["predicate_atoms"]}
    for residual in state["residual_comparisons"]:
        if residual.get("status") != "contested":
            continue
        left = atom_by_id.get(residual.get("left_atom_id"))
        right = atom_by_id.get(residual.get("right_atom_id"))
        item = {
            "id": stable_id("contest", {"residual": residual["id"]}),
            "status": "contested",
            "residual_id": residual["id"],
            "atom_ids": [residual.get("left_atom_id"), residual.get("right_atom_id")],
            "predicate": left.get("predicate") if left else None,
            "receipt_ids": residual.get("receipt_ids", []),
        }
        _join_item(state["contested_items"], item, state["status_history"], delta_id)
        for atom in (left, right):
            if atom and atom.get("status") != "contested":
                old = atom.get("status")
                atom["status"] = "contested"
                atom["receipt_ids"] = sorted(set(atom.get("receipt_ids", [])) | set(residual.get("receipt_ids", [])))
                state["status_history"].append(_history(atom["id"], old, "contested", delta_id, atom["receipt_ids"]))


def _derive_pnf_residual_receipts(state: dict[str, Any], delta_id: str) -> None:
    receipt_by_atom = {
        str(item.get("atom_id")): item
        for item in state.get("pnf_emission_receipts", [])
        if item.get("atom_id")
    }
    receipt_index = {
        str(item.get("id")): item
        for item in state.get("pnf_residual_receipts", [])
        if item.get("id")
    }
    for residual in state.get("residual_comparisons", []):
        if residual.get("status") != "contested":
            continue
        left = receipt_by_atom.get(str(residual.get("left_atom_id")))
        right = receipt_by_atom.get(str(residual.get("right_atom_id")))
        missing = []
        if left is None:
            missing.append("leftEmissionReceipt")
        if right is None:
            missing.append("rightEmissionReceipt")
        payload = {
            "residual_id": residual.get("id"),
            "left_emission_receipt_id": left.get("id") if left else None,
            "right_emission_receipt_id": right.get("id") if right else None,
            "residual_level": residual.get("residual_level", "contradiction"),
            "relation": residual.get("relation"),
            "residual_computation_profile": "sensiblaw.conversation_vm.reducer.v0_1",
            "hecke_candidate_pool_receipt_id": None,
            "runtime_provider_status": "missingHeckeCandidatePoolReceiptId",
        }
        if missing:
            payload["missing_fields"] = missing
        receipt_item = {
            "id": stable_id("pnfres", payload),
            "schema": "sl.pnf_residual_receipt.v0_1",
            "status": "diagnostic" if missing else "available_without_hecke_candidate_pool",
            "left_atom_id": residual.get("left_atom_id"),
            "right_atom_id": residual.get("right_atom_id"),
            "left_emission_receipt_id": payload["left_emission_receipt_id"],
            "right_emission_receipt_id": payload["right_emission_receipt_id"],
            "residual_id": residual.get("id"),
            "residual_level": payload["residual_level"],
            "relation": residual.get("relation"),
            "payload": payload,
            "receipt_ids": sorted(set(residual.get("receipt_ids") or [])),
        }
        _join_item(state["pnf_residual_receipts"], receipt_item, state["status_history"], delta_id, receipt_index)


def _atom_signature(atom: dict[str, Any]) -> tuple[str | None, str]:
    roles = atom.get("roles")
    qualifiers = atom.get("qualifiers")
    if isinstance(roles, dict):
        role_parts = []
        for key in sorted(roles):
            if key == "action":
                continue
            value = _role_value(roles.get(key))
            if value:
                role_parts.append((key, value))
        qualifier_parts = []
        if isinstance(qualifiers, dict):
            qualifier_parts = [
                (key, str(value))
                for key, value in sorted(qualifiers.items())
                if key != "polarity" and value not in (None, "", "unknown")
            ]
        return (
            str(atom.get("domain") or ""),
            json.dumps(
                {
                    "structural_signature": atom.get("structural_signature") or atom.get("predicate"),
                    "predicate": atom.get("predicate"),
                    "roles": role_parts,
                    "qualifiers": qualifier_parts,
                },
                sort_keys=True,
            ),
        )
    return (
        atom.get("predicate"),
        json.dumps(atom.get("arguments") or [], sort_keys=True),
    )


def _role_value(role: object) -> str | None:
    if isinstance(role, dict):
        value = role.get("value")
        if value is not None:
            return str(value)
    if role is not None:
        return str(role)
    return None


def _derive_cross_atom_residuals(
    state: dict[str, Any],
    delta_id: str,
    *,
    touched_atom_ids: set[str] | None = None,
) -> None:
    atoms = state["predicate_atoms"]
    if touched_atom_ids == set():
        return
    if touched_atom_ids is None:
        candidate_atoms = atoms
    else:
        candidate_atoms = [atom for atom in atoms if str(atom.get("id")) in touched_atom_ids]
    atoms_by_signature: dict[tuple[str | None, str], list[dict[str, Any]]] = {}
    for atom in atoms:
        atoms_by_signature.setdefault(_atom_signature(atom), []).append(atom)

    seen_pairs: set[tuple[str, str]] = set()
    residual_index = {str(item.get("id")): item for item in state["residual_comparisons"] if item.get("id")}
    for left in candidate_atoms:
        for right in atoms_by_signature.get(_atom_signature(left), []):
            if left.get("id") == right.get("id"):
                continue
            if left.get("polarity") == right.get("polarity"):
                continue
            left_id, right_id = sorted([str(left["id"]), str(right["id"])])
            pair_key = (left_id, right_id)
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)
            residual = {
                "id": stable_id("resid", {"left": left_id, "right": right_id, "relation": "polarity-conflict"}),
                "left_atom_id": left_id,
                "right_atom_id": right_id,
                "relation": "polarity-conflict",
                "status": "contested",
                "receipt_ids": sorted(set(left.get("receipt_ids", [])) | set(right.get("receipt_ids", []))),
            }
            _join_item(state["residual_comparisons"], residual, state["status_history"], delta_id, residual_index)

    for left in candidate_atoms:
        for right in atoms:
            if left.get("id") == right.get("id"):
                continue
            if not _is_classification_tension(left, right):
                continue
            left_id, right_id = sorted([str(left["id"]), str(right["id"])])
            pair_key = (left_id, right_id)
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)
            residual = {
                "id": stable_id("resid", {"left": left_id, "right": right_id, "relation": "classification-tension"}),
                "left_atom_id": left_id,
                "right_atom_id": right_id,
                "relation": "classification-tension",
                "status": "contested",
                "residual_level": "contradiction",
                "receipt_ids": sorted(set(left.get("receipt_ids", [])) | set(right.get("receipt_ids", []))),
            }
            _join_item(state["residual_comparisons"], residual, state["status_history"], delta_id, residual_index)


def _is_classification_tension(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if left.get("predicate") != "be/classify" or right.get("predicate") != "be/classify":
        return False
    if left.get("domain") != "classification" or right.get("domain") != "classification":
        return False
    if left.get("polarity") == right.get("polarity"):
        return False
    left_roles = left.get("roles") if isinstance(left.get("roles"), dict) else {}
    right_roles = right.get("roles") if isinstance(right.get("roles"), dict) else {}
    left_subject = _role_value(left_roles.get("agent"))
    right_subject = _role_value(right_roles.get("agent"))
    left_theme = _role_value(left_roles.get("theme"))
    right_theme = _role_value(right_roles.get("theme"))
    return bool(left_subject and left_subject == right_subject and left_theme and right_theme and left_theme != right_theme)


def _derive_blocked_promotions(state: dict[str, Any], delta_id: str) -> None:
    blocked_gate_names = {gate.get("name") for gate in state["promotion_gates"] if gate.get("status") == "blocked"}
    if not blocked_gate_names:
        return
    for atom in state["predicate_atoms"]:
        if atom.get("status") == "promoted":
            blocker = {
                "id": stable_id("block", {"atom_id": atom["id"], "gates": sorted(blocked_gate_names)}),
                "status": "blocked",
                "atom_id": atom["id"],
                "missing_gates": sorted(blocked_gate_names),
                "receipt_ids": atom.get("receipt_ids", []),
            }
            _join_item(state["blockers"], blocker, state["status_history"], delta_id)


def _history(item_id: str, previous: str | None, current: str | None, delta_id: str, receipt_ids: list[str]) -> dict[str, Any]:
    return {
        "id": stable_id("hist", {"item_id": item_id, "previous": previous, "current": current, "delta_id": delta_id}),
        "item_id": item_id,
        "previous_status": previous,
        "current_status": current,
        "delta_id": delta_id,
        "receipt_ids": sorted(receipt_ids),
    }


class _MetricSpan:
    def __init__(self, callback: Any | None, stage: str, **fields: Any) -> None:
        self.callback = callback
        self.stage = stage
        self.fields = fields
        self.started = 0.0

    def __enter__(self) -> "_MetricSpan":
        self.started = time.perf_counter()
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self.callback is None:
            return
        row = {
            "component": "conversation_vm.reducer",
            "stage": self.stage,
            "elapsed_ms": round((time.perf_counter() - self.started) * 1000, 6),
            **self.fields,
        }
        try:
            self.callback(row)
        except Exception:
            pass
