"""Monotone join reducer for Conversation VM state."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .schema import STATE_SCHEMA, stable_id

COLLECTIONS = (
    "sources",
    "excerpts",
    "statements",
    "observations",
    "predicate_atoms",
    "predicate_pnfs",
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


def step_state(state: dict[str, Any] | None, delta: dict[str, Any]) -> dict[str, Any]:
    next_state = deepcopy(state) if state else empty_state()
    delta_id = delta["id"]
    if delta_id in next_state["applied_delta_ids"]:
        return next_state

    for name in COLLECTIONS:
        for item in delta.get(name, []):
            _join_item(next_state[name], item, next_state["status_history"], delta_id)

    _derive_cross_atom_residuals(next_state, delta_id)
    _derive_contested_items(next_state, delta_id)
    _derive_blocked_promotions(next_state, delta_id)
    next_state["applied_delta_ids"].append(delta_id)
    next_state["applied_delta_ids"].sort()
    next_state["compact_payload_metadata"] = {
        "delta_count": len(next_state["applied_delta_ids"]),
        "source_count": len(next_state["sources"]),
        "atom_count": len(next_state["predicate_atoms"]),
        "contested_count": len(next_state["contested_items"]),
        "abstention_count": len(next_state["abstentions"]),
    }
    return next_state


def _join_item(collection: list[dict[str, Any]], item: dict[str, Any], history: list[dict[str, Any]], delta_id: str) -> None:
    existing = next((candidate for candidate in collection if candidate.get("id") == item.get("id")), None)
    if existing is None:
        collection.append(deepcopy(item))
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


def _derive_cross_atom_residuals(state: dict[str, Any], delta_id: str) -> None:
    atoms = state["predicate_atoms"]
    for left_index, left in enumerate(atoms):
        for right in atoms[left_index + 1 :]:
            if left.get("predicate") != right.get("predicate"):
                continue
            if left.get("arguments") != right.get("arguments"):
                continue
            if left.get("polarity") == right.get("polarity"):
                continue
            residual = {
                "id": stable_id("resid", {"left": left["id"], "right": right["id"], "relation": "polarity-conflict"}),
                "left_atom_id": left["id"],
                "right_atom_id": right["id"],
                "relation": "polarity-conflict",
                "status": "contested",
                "receipt_ids": sorted(set(left.get("receipt_ids", [])) | set(right.get("receipt_ids", []))),
            }
            _join_item(state["residual_comparisons"], residual, state["status_history"], delta_id)


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
