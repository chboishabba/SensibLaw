from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable, List, Optional, Set, Tuple

from src.obligations import ObligationAtom


@dataclass(frozen=True)
class ObligationIdentity:
    """Stable, deterministic identity for an obligation atom."""

    obligation_type: str
    modality: str
    actor: Optional[str]
    action: Optional[str]
    obj: Optional[str]
    reference_hashes: Tuple[str, ...]
    condition_types: Tuple[str, ...]
    clause_index: int
    identity_hash: str


def compute_obligation_identity(obligation: ObligationAtom, clause_index: int) -> ObligationIdentity:
    """Pure function: derive an ObligationIdentity from an ObligationAtom."""

    ref_hashes = tuple(sorted(obligation.reference_identities))
    condition_types = tuple(sorted({getattr(c, "type", str(c)) for c in obligation.conditions}))
    actor = obligation.actor.normalized if getattr(obligation, "actor", None) else None
    action = obligation.action.normalized if getattr(obligation, "action", None) else None
    obj = obligation.obj.normalized if getattr(obligation, "obj", None) else None
    payload = {
        "type": obligation.type,
        "modality": obligation.modality,
        "actor": actor,
        "action": action,
        "object": obj,
        "refs": ref_hashes,
        "conditions": condition_types,
    }
    identity_hash = _hash_payload(payload)
    return ObligationIdentity(
        obligation_type=obligation.type,
        modality=obligation.modality,
        actor=actor,
        action=action,
        obj=obj,
        reference_hashes=ref_hashes,
        condition_types=condition_types,
        clause_index=clause_index,
        identity_hash=identity_hash,
    )


@dataclass(frozen=True)
class ObligationDiff:
    added: Set[str]
    removed: Set[str]
    unchanged: Set[str]


def diff_obligations(lhs: Iterable[ObligationIdentity], rhs: Iterable[ObligationIdentity]) -> ObligationDiff:
    left = {o.identity_hash for o in lhs}
    right = {o.identity_hash for o in rhs}
    added = right - left
    removed = left - right
    unchanged = left & right
    return ObligationDiff(added=added, removed=removed, unchanged=unchanged)


def compute_identities(obligations: Iterable) -> List[ObligationIdentity]:
    """Helper to compute identities for an ordered iterable of obligations."""

    return [compute_obligation_identity(obligation, idx) for idx, obligation in enumerate(obligations)]


def _hash_payload(payload: dict) -> str:
    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(payload_json.encode("utf-8")).hexdigest()


__all__ = ["ObligationIdentity", "compute_obligation_identity", "ObligationDiff", "diff_obligations"]
