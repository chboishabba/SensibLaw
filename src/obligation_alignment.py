from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

from src.obligation_identity import ObligationIdentity, compute_identities
from src.obligations import ObligationAtom, obligation_to_dict

ALIGNMENT_SCHEMA_VERSION = "obligation.alignment.v1"


@dataclass(frozen=True)
class AlignmentDelta:
    identity_hash: str
    old: dict
    new: dict
    changes: Dict[str, Tuple[Optional[object], Optional[object]]]


@dataclass(frozen=True)
class AlignmentReport:
    added: List[dict]
    removed: List[dict]
    unchanged: List[dict]
    modified: List[AlignmentDelta]


def _metadata_view(ob: ObligationAtom) -> Dict[str, object]:
    return {
        "actor": ob.actor.normalized if ob.actor else None,
        "action": ob.action.normalized if ob.action else None,
        "object": ob.obj.normalized if ob.obj else None,
        "modality": ob.modality,
        "reference_identities": tuple(sorted(ob.reference_identities)),
        "scopes": tuple(sorted((s.category, s.normalized) for s in ob.scopes)),
        "lifecycle": tuple(sorted((l.kind, l.normalized) for l in ob.lifecycle)),
    }


def _diff_metadata(old_meta: Dict[str, object], new_meta: Dict[str, object]) -> Dict[str, Tuple[Optional[object], Optional[object]]]:
    changes: Dict[str, Tuple[Optional[object], Optional[object]]] = {}
    keys = set(old_meta) | set(new_meta)
    for key in sorted(keys):
        if old_meta.get(key) != new_meta.get(key):
            changes[key] = (old_meta.get(key), new_meta.get(key))
    return changes


def align_obligations(old: Iterable[ObligationAtom], new: Iterable[ObligationAtom]) -> AlignmentReport:
    old_list = list(old)
    new_list = list(new)
    old_ids = compute_identities(old_list)
    new_ids = compute_identities(new_list)

    id_to_ob_old: Dict[str, ObligationAtom] = {oid.identity_hash: ob for oid, ob in zip(old_ids, old_list)}
    id_to_ob_new: Dict[str, ObligationAtom] = {nid.identity_hash: ob for nid, ob in zip(new_ids, new_list)}

    old_keys = set(id_to_ob_old)
    new_keys = set(id_to_ob_new)

    added_keys = sorted(new_keys - old_keys)
    removed_keys = sorted(old_keys - new_keys)
    unchanged_keys = sorted(old_keys & new_keys)

    modified: List[AlignmentDelta] = []
    unchanged: List[dict] = []
    for key in unchanged_keys:
        old_meta = _metadata_view(id_to_ob_old[key])
        new_meta = _metadata_view(id_to_ob_new[key])
        changes = _diff_metadata(old_meta, new_meta)
        if changes:
            modified.append(
                AlignmentDelta(
                    identity_hash=key,
                    old=obligation_to_dict(id_to_ob_old[key]),
                    new=obligation_to_dict(id_to_ob_new[key]),
                    changes=changes,
                )
            )
        else:
            unchanged.append(obligation_to_dict(id_to_ob_old[key]))

    added = [obligation_to_dict(id_to_ob_new[k]) for k in added_keys]
    removed = [obligation_to_dict(id_to_ob_old[k]) for k in removed_keys]
    return AlignmentReport(added=added, removed=removed, unchanged=unchanged, modified=modified)


def alignment_to_payload(report: AlignmentReport) -> dict:
    def _changes_as_list(delta: AlignmentDelta) -> list[dict]:
        return [
            {"field": field, "old": old_val, "new": new_val}
            for field, (old_val, new_val) in sorted(delta.changes.items(), key=lambda kv: kv[0])
        ]

    return {
        "version": ALIGNMENT_SCHEMA_VERSION,
        "added": report.added,
        "removed": report.removed,
        "unchanged": report.unchanged,
        "modified": [
            {
                "identity_hash": delta.identity_hash,
                "old": delta.old,
                "new": delta.new,
                "changes": _changes_as_list(delta),
            }
            for delta in report.modified
        ],
    }


__all__ = [
    "AlignmentReport",
    "AlignmentDelta",
    "ALIGNMENT_SCHEMA_VERSION",
    "align_obligations",
    "alignment_to_payload",
]
