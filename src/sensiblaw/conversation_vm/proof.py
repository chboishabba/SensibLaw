"""Queryable proof and compact context payload builders."""

from __future__ import annotations

from typing import Any

from .schema import CONTEXT_PAYLOAD_SCHEMA, PROOF_SURFACE_SCHEMA, stable_id


def build_proof_surface(state: dict[str, Any], query: str | None = None) -> dict[str, Any]:
    atoms = _filter_by_query(state.get("predicate_atoms", []), query)
    atom_ids = {atom["id"] for atom in atoms}
    residuals = [
        item
        for item in state.get("residual_comparisons", [])
        if item.get("left_atom_id") in atom_ids or item.get("right_atom_id") in atom_ids
    ]
    return {
        "schema": PROOF_SURFACE_SCHEMA,
        "id": stable_id("proof", {"state_id": state.get("id"), "query": query, "atoms": sorted(atom_ids)}),
        "state_id": state.get("id"),
        "query": query,
        "sources": state.get("sources", []),
        "excerpts": state.get("excerpts", []),
        "statements": state.get("statements", []),
        "observations": state.get("observations", []),
        "predicate_atoms": atoms,
        "predicate_pnfs": [item for item in state.get("predicate_pnfs", []) if item.get("atom_id") in atom_ids],
        "residual_comparisons": residuals,
        "promotion_gates": state.get("promotion_gates", []),
        "proof_obligations": state.get("proof_obligations", []),
        "blockers": state.get("blockers", []),
        "abstentions": state.get("abstentions", []),
        "contested_items": state.get("contested_items", []),
    }


def build_context_payload(state: dict[str, Any], query: str | None = None, limit: int = 12) -> dict[str, Any]:
    surface = build_proof_surface(state, query=query)
    atoms = surface["predicate_atoms"][:limit]
    atom_ids = {atom["id"] for atom in atoms}
    return {
        "schema": CONTEXT_PAYLOAD_SCHEMA,
        "id": stable_id("ctx", {"surface_id": surface["id"], "limit": limit}),
        "proof_surface_id": surface["id"],
        "query": query,
        "items": [
            {
                "atom": atom,
                "pnf": next((pnf for pnf in surface["predicate_pnfs"] if pnf.get("atom_id") == atom["id"]), None),
                "residuals": [
                    residual
                    for residual in surface["residual_comparisons"]
                    if residual.get("left_atom_id") == atom["id"] or residual.get("right_atom_id") == atom["id"]
                ],
            }
            for atom in atoms
        ],
        "missing_evidence": surface["proof_obligations"],
        "abstentions": surface["abstentions"],
        "contested_items": [item for item in surface["contested_items"] if any(atom_id in item.get("atom_ids", []) for atom_id in atom_ids)],
        "metadata": {
            "opaque_summary": False,
            "item_count": len(atoms),
            "source_count": len(surface["sources"]),
        },
    }


def _filter_by_query(items: list[dict[str, Any]], query: str | None) -> list[dict[str, Any]]:
    if not query:
        return list(items)
    needle = query.lower()
    return [
        item
        for item in items
        if needle in item.get("predicate", "").lower()
        or any(needle in str(argument).lower() for argument in item.get("arguments", []))
    ]
